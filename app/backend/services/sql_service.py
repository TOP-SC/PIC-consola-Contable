"""Acceso a SQL Server (Tango) — misma lógica que txtARBA_Contable, con lecturas NOLOCK."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

from config import Settings
from models.schemas import BranchConnection, ImpuestoRow, parse_sql_date

logger = logging.getLogger("arba.sql")

# Misma query que la app original + WITH (NOLOCK) para no bloquear tablas/vistas de Tango
QUERY_TEMPLATE = (
    "select DB_NAME() as [LOCAL],[T_COMP],[N_COMP],[FECHA_EMIS],[RAZON_SOCI],[IDENTIFTRI],"
    "[IMPORTE_GRAVADO],[IMPORTE],cast([ALICUOTA] as int) as [ALICUOTA],[DESC_ALIC],"
    "[PORCE_IMP],[IMPUESTO] from VW_ImpuestosReg2 WITH (NOLOCK) where [FECHA_EMIS] >= '{desde}' "
    "and [FECHA_EMIS] <= '{hasta}'  and upper([DESC_ALIC]) like '%BS%AS%' "
    "ORDER BY [T_COMP],[N_COMP];"
)

READ_UNCOMMITTED = "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;"


class SqlCursor:
    """Wrapper mínimo común para pyodbc / pymssql."""

    def __init__(self, cursor, backend: str):
        self._cur = cursor
        self.backend = backend
        self.description = None

    def execute(self, sql: str, params=None):
        if params is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, params)
        self.description = getattr(self._cur, "description", None)
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()


def _has_pymssql() -> bool:
    try:
        import pymssql  # noqa: F401
        return True
    except Exception:
        return False


def _has_pyodbc() -> bool:
    try:
        import pyodbc  # noqa: F401
        return True
    except Exception:
        return False


def resolve_backend(settings: Settings) -> str:
    pref = (settings.sql_backend or "auto").lower().strip()
    if pref == "pymssql":
        if not _has_pymssql():
            raise RuntimeError("sql_backend=pymssql pero pymssql no está disponible")
        return "pymssql"
    if pref == "pyodbc":
        if not _has_pyodbc():
            raise RuntimeError("sql_backend=pyodbc pero pyodbc no está disponible")
        return "pyodbc"
    # auto: prioriza pymssql (portable, sin ODBC instalado en el server)
    if _has_pymssql():
        return "pymssql"
    if _has_pyodbc():
        return "pyodbc"
    raise RuntimeError("No hay backend SQL disponible (pymssql/pyodbc)")


@contextmanager
def open_connection(
    settings: Settings,
    server: str,
    database: str,
    user: str,
    password: str,
) -> Iterator[tuple[Any, SqlCursor, str]]:
    backend = resolve_backend(settings)
    if backend == "pymssql":
        import pymssql

        conn = pymssql.connect(
            server=server,
            user=user,
            password=password,
            database=database,
            login_timeout=8,
            timeout=settings.query_timeout,
            tds_version="7.4",
        )
        cur = conn.cursor()
        wrapped = SqlCursor(cur, backend)
        try:
            wrapped.execute(READ_UNCOMMITTED)
            yield conn, wrapped, backend
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return

    import pyodbc

    conn = pyodbc.connect(
        settings._odbc_conn(server, database, user, password),
        timeout=max(8, min(settings.query_timeout, 30)),
    )
    cur = conn.cursor()
    try:
        cur.timeout = settings.query_timeout
    except Exception:
        pass
    wrapped = SqlCursor(cur, backend)
    try:
        wrapped.execute(READ_UNCOMMITTED)
        yield conn, wrapped, backend
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_available_drivers() -> list[str]:
    info = []
    if _has_pymssql():
        info.append("pymssql (sin ODBC)")
    if _has_pyodbc():
        try:
            import pyodbc
            info.extend(list(pyodbc.drivers()))
        except Exception:
            info.append("pyodbc")
    return info


def test_central(settings: Settings) -> tuple[bool, str]:
    try:
        backend = resolve_backend(settings)
    except Exception as exc:
        return False, str(exc)

    try:
        with open_connection(
            settings,
            settings.central_server,
            settings.central_database,
            settings.central_user,
            settings.central_password,
        ) as (_conn, cur, backend_used):
            cur.execute("SELECT @@SERVERNAME, DB_NAME(), SYSTEM_USER")
            server, db, user = cur.fetchone()
        return True, f"Conectado a {server} / {db} (user {user}) via {backend_used}"
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if any(x in low for x in ("08001", "timeout", "not found", "no existe", "refused", "unreachable")):
            return (
                False,
                f"No se alcanza el SQL {settings.central_server}. "
                f"Esta PC tiene que estar en la misma red/VPN que el servidor Contable. Detalle: {msg}",
            )
        return False, msg


def fetch_branches(settings: Settings) -> list[BranchConnection]:
    with open_connection(
        settings,
        settings.central_server,
        settings.central_database,
        settings.central_user,
        settings.central_password,
    ) as (_conn, cur, backend):
        sql = "EXECUTE dbo.SP_ConexionListarSucursalMultinivel %s, %s" if backend == "pymssql" else "EXECUTE dbo.SP_ConexionListarSucursalMultinivel ?, ?"
        param_attempts = [
            (settings.sp_param_1, settings.sp_param_2),
            (
                settings.sp_param_1,
                int(settings.sp_param_2) if str(settings.sp_param_2).isdigit() else settings.sp_param_2,
            ),
        ]
        last_err: Exception | None = None
        rows = None
        description = None
        for params in param_attempts:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
                description = cur.description
                break
            except Exception as exc:
                last_err = exc

        if rows is None:
            raise RuntimeError(f"Error ejecutando SP de sucursales: {last_err}")
        if not rows:
            return []

        branches: list[BranchConnection] = []
        for row in rows:
            data = {description[i][0].lower(): row[i] for i in range(len(description))}

            def pick(*keys, default=""):
                for k in keys:
                    if k.lower() in data and data[k.lower()] is not None:
                        return str(data[k.lower()]).strip()
                return default

            servidor = pick("servidor", "server", "data_source")
            catalogo = pick("catalogo", "catalog", "base", "database", "initial catalog")
            usuario = pick("usuario", "user", "user id", "uid")
            password = pick("password", "clave", "pwd", "pass")
            if not servidor or not catalogo:
                continue
            branches.append(
                BranchConnection(
                    id_conexion=pick("idconexion", "id_conexion") or None,
                    codigo=pick("codigo", "codsucursal") or None,
                    nombre=pick("nombre", "local") or None,
                    razon_social=pick("razonsocial", "razon_social", "razon_soci") or None,
                    servidor=servidor,
                    catalogo=catalogo,
                    usuario=usuario or settings.central_user,
                    password=password or settings.central_password,
                    local=pick("local", "nombre") or None,
                )
            )
        return branches


def fetch_impuestos_branch(
    settings: Settings,
    branch: BranchConnection,
    desde: date,
    hasta: date,
) -> list[ImpuestoRow]:
    with open_connection(
        settings,
        branch.servidor,
        branch.catalogo,
        branch.usuario,
        branch.password,
    ) as (_conn, cur, _backend):
        attempts = [
            QUERY_TEMPLATE.format(desde=desde.strftime("%Y-%m-%d"), hasta=hasta.strftime("%Y-%m-%d")),
            QUERY_TEMPLATE.format(desde=desde.strftime("%Y%m%d"), hasta=hasta.strftime("%Y%m%d")),
        ]
        last_err: Exception | None = None
        fetched = None
        description = None
        for sql in attempts:
            try:
                cur.execute(sql)
                fetched = cur.fetchall()
                description = cur.description
                break
            except Exception as exc:
                last_err = exc

        if fetched is None:
            raise RuntimeError(last_err)

        result: list[ImpuestoRow] = []
        for row in fetched:
            data = {description[i][0].upper(): row[i] for i in range(len(description))}
            result.append(
                ImpuestoRow(
                    local=str(data.get("LOCAL") or branch.local or branch.catalogo or ""),
                    t_comp=str(data.get("T_COMP") or "").strip(),
                    n_comp=str(data.get("N_COMP") or "").strip(),
                    fecha_emis=parse_sql_date(data.get("FECHA_EMIS")),
                    razon_soci=(str(data["RAZON_SOCI"]).strip() if data.get("RAZON_SOCI") is not None else None),
                    identiftri=str(data.get("IDENTIFTRI") or "").strip(),
                    importe_gravado=float(data.get("IMPORTE_GRAVADO") or 0),
                    importe=float(data.get("IMPORTE") or 0),
                    alicuota=int(data["ALICUOTA"]) if data.get("ALICUOTA") is not None else None,
                    desc_alic=(str(data["DESC_ALIC"]).strip() if data.get("DESC_ALIC") is not None else None),
                    porce_imp=float(data["PORCE_IMP"]) if data.get("PORCE_IMP") is not None else None,
                    impuesto=(str(data["IMPUESTO"]).strip() if data.get("IMPUESTO") is not None else None),
                )
            )
        return result


def search_all_branches(
    settings: Settings,
    desde: date,
    hasta: date,
) -> tuple[list[ImpuestoRow], list[str], int, int]:
    ok_central, msg = test_central(settings)
    if not ok_central:
        raise RuntimeError(msg)

    branches = fetch_branches(settings)
    if not branches:
        raise RuntimeError(
            "El SP no devolvió sucursales. Revisá SP_PARAM_1 / SP_PARAM_2 en .env"
        )

    all_rows: list[ImpuestoRow] = []
    errors: list[str] = []
    ok = 0
    fail = 0

    for branch in branches:
        label = branch.nombre or branch.catalogo or branch.servidor
        try:
            rows = fetch_impuestos_branch(settings, branch, desde, hasta)
            all_rows.extend(rows)
            ok += 1
            logger.info("OK %s → %s filas", label, len(rows))
        except Exception as exc:
            fail += 1
            err = f"Error en {label} -> {type(exc).__name__}(): {exc}"
            errors.append(err)
            logger.exception(err)
            _append_log(settings, err)

    all_rows.sort(key=lambda r: (r.t_comp, r.n_comp, r.fecha_emis.isoformat()))
    return all_rows, errors, ok, fail


def _append_log(settings: Settings, message: str) -> None:
    settings.logs_path.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    path = settings.logs_path / f"log_{datetime.now():%Y%m%d}.txt"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")

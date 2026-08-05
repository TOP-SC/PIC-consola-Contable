"""Generación del archivo de texto IBPER para ARBA (mismo layout que txtARBA_Contable)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from models.schemas import ImpuestoRow

LINE_WIDTH = 61
SITUACION = "a"


def _fmt_amount(value: float, width: int, force_negative: bool = False) -> str:
    neg = force_negative or value < 0
    body = f"{abs(float(value)):.2f}"
    if neg:
        return ("-" + body.zfill(width - 1))[:width]
    return body.zfill(width)


def _split_comprobante(n_comp: str) -> tuple[str, str]:
    """Separa punto de venta (4) y número (8) desde N_COMP de Tango."""
    raw = (n_comp or "").strip().replace(" ", "")
    if "-" in raw:
        left, right = raw.split("-", 1)
        pv = "".join(ch for ch in left if ch.isdigit()).zfill(4)[-4:]
        nro = "".join(ch for ch in right if ch.isdigit()).zfill(8)[-8:]
        return pv, nro

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 12:
        return digits[:4].zfill(4), digits[-8:].zfill(8)
    if len(digits) > 8:
        return digits[:-8].zfill(4)[-4:], digits[-8:].zfill(8)
    return "0000", digits.zfill(8)


def _normalize_cuit(identiftri: str) -> str:
    s = (identiftri or "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    if len(s) == 13 and s[2] == "-" and s[11] == "-":
        return s
    return s[:13].ljust(13)[:13]


def format_ibper_line(row: ImpuestoRow) -> str:
    cuit = _normalize_cuit(row.identiftri)
    fecha = row.fecha_emis.strftime("%d/%m/%Y")
    t_comp = (row.t_comp or "").strip().upper()[:2].ljust(2)[:2]
    pv, nro = _split_comprobante(row.n_comp)

    # Notas de crédito: montos con signo negativo (como la app original)
    force_neg = t_comp in {"CA", "CB", "CC", "NC", "ND"}
    grav_val = -abs(row.importe_gravado) if force_neg else row.importe_gravado
    imp_val = -abs(row.importe) if force_neg else row.importe
    grav = _fmt_amount(grav_val, 12, force_negative=force_neg)
    imp = _fmt_amount(imp_val, 11, force_negative=force_neg)

    line = f"{cuit}{fecha}{t_comp}{pv}{nro}{grav}{imp}{SITUACION}"
    if len(line) != LINE_WIDTH:
        raise ValueError(f"Línea IBPER inválida ({len(line)} chars): {line}")
    return line


def month_folder_name(d: date) -> str:
    # es-AR: "agosto - 2026"
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return f"{months[d.month - 1]} - {d.year}"


def output_filename(d: date) -> str:
    # Misma idea que ToShortDateString es-AR: sin ceros a la izquierda
    return f"{d.day}-{d.month}-{d.year} ibper.txt"


def build_ibper_bytes(rows: list[ImpuestoRow]) -> bytes:
    """Genera el contenido descargable sin escribirlo en el servidor."""
    lines = [format_ibper_line(r) for r in rows]
    content = "\r\n".join(lines)
    if lines:
        content += "\r\n"
    return content.encode("latin-1", errors="replace")


def write_ibper_file(rows: list[ImpuestoRow], output_root: Path, ref_date: date) -> Path:
    folder = output_root / month_folder_name(ref_date)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / output_filename(ref_date)

    path.write_bytes(build_ibper_bytes(rows))
    return path


def parse_ibper_line(line: str) -> ImpuestoRow | None:
    line = line.strip()
    if len(line) < LINE_WIDTH:
        return None
    line = line[:LINE_WIDTH]
    try:
        cuit = line[0:13]
        fecha = date(int(line[19:23]), int(line[16:18]), int(line[13:15]))
        t_comp = line[23:25]
        pv = line[25:29]
        nro = line[29:37]
        grav_raw = line[37:49].replace(",", ".").strip()
        imp_raw = line[49:60].replace(",", ".").strip()
        # Algunas líneas históricas pueden traer signos raros
        grav_raw = grav_raw.replace("--", "-")
        imp_raw = imp_raw.replace("--", "-")
        grav = float(grav_raw)
        imp = float(imp_raw)
    except Exception:
        return None
    return ImpuestoRow(
        local="DEMO",
        t_comp=t_comp,
        n_comp=f"{pv}-{nro}",
        fecha_emis=fecha,
        razon_soci=None,
        identiftri=cuit,
        importe_gravado=grav,
        importe=imp,
        alicuota=None,
        desc_alic="BS AS (demo)",
        porce_imp=None,
        impuesto=None,
    )

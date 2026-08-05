from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Carpeta writable de la app (junto al .exe o carpeta app/)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Recursos embebidos (frontend) en build PyInstaller."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_dir()


BASE_DIR = app_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(app_dir() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    central_server: str = "10.0.0.4"
    central_database: str = "AUXILIAR"
    central_user: str = "Batch"
    central_password: str = ""

    sp_param_1: str = "SC2017"
    sp_param_2: str = "1"

    output_root: str = "./Documentos"
    logs_root: str = "./Logs"
    odbc_driver: str = "ODBC Driver 18 for SQL Server"
    # auto | pymssql | pyodbc  (pymssql no necesita instalar ODBC en el servidor)
    sql_backend: str = "auto"
    query_timeout: int = 60

    @property
    def output_path(self) -> Path:
        p = Path(self.output_root)
        if not p.is_absolute():
            p = app_dir() / p
        return p

    @property
    def logs_path(self) -> Path:
        p = Path(self.logs_root)
        if not p.is_absolute():
            p = app_dir() / p
        return p

    def resolve_driver(self) -> str:
        try:
            import pyodbc
        except ImportError:
            return self.odbc_driver

        installed = list(pyodbc.drivers())
        if self.odbc_driver in installed:
            return self.odbc_driver

        preferred = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server",
        ]
        for name in preferred:
            if name in installed:
                return name
        sqlish = [d for d in installed if "SQL Server" in d]
        return sqlish[-1] if sqlish else self.odbc_driver

    def _odbc_conn(self, server: str, catalog: str, user: str, password: str) -> str:
        driver = self.resolve_driver()
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={catalog};"
            f"UID={user};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

    def central_connection_string(self) -> str:
        return self._odbc_conn(
            self.central_server,
            self.central_database,
            self.central_user,
            self.central_password,
        )

    def branch_connection_string(self, server: str, catalog: str, user: str, password: str) -> str:
        return self._odbc_conn(server, catalog, user, password)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()

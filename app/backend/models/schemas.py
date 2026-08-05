from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BranchConnection(BaseModel):
    id_conexion: Optional[str] = None
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    razon_social: Optional[str] = None
    servidor: str
    catalogo: str
    usuario: str
    password: str
    local: Optional[str] = None


class ImpuestoRow(BaseModel):
    local: Optional[str] = None
    t_comp: str
    n_comp: str
    fecha_emis: date
    razon_soci: Optional[str] = None
    identiftri: str
    importe_gravado: float
    importe: float
    alicuota: Optional[int] = None
    desc_alic: Optional[str] = None
    porce_imp: Optional[float] = None
    impuesto: Optional[str] = None


class SearchRequest(BaseModel):
    desde: date
    hasta: date
    demo: bool = False


class SearchResponse(BaseModel):
    total: int
    rows: list[ImpuestoRow]
    branches_ok: int = 0
    branches_error: int = 0
    errors: list[str] = Field(default_factory=list)
    demo: bool = False


class GenerateRequest(BaseModel):
    desde: date
    hasta: date
    rows: list[ImpuestoRow]
    demo: bool = False


class GenerateResponse(BaseModel):
    ok: bool
    path: str
    filename: str
    folder: str
    lines: int
    message: str


class ExcelRequest(BaseModel):
    rows: list[ImpuestoRow]


class StatusResponse(BaseModel):
    ok: bool
    central_reachable: bool
    message: str
    driver: str
    output_root: str
    details: dict[str, Any] = Field(default_factory=dict)


def parse_sql_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Fecha inválida: {value!r}")

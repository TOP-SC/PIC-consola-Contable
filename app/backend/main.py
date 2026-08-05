from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from config import get_settings, reload_settings, resource_dir
from models.schemas import GenerateRequest, SearchRequest, SearchResponse, StatusResponse
from services.ibper import build_ibper_bytes, output_filename
from services import sql_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arba")

APP_VERSION = "2.0.2"

app = FastAPI(title="PIC - Plataforma Integral Contable", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = resource_dir() / "frontend"


@app.middleware("http")
async def no_cache(request: Request, call_next):
    """Los usuarios abren siempre por HTTP: evitamos servir una UI vieja cacheada."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-PIC-Version"] = APP_VERSION
    return response


@app.get("/api/health")
def health():
    return {"ok": True, "version": APP_VERSION}


@app.get("/api/status", response_model=StatusResponse)
def status():
    settings = reload_settings()
    settings.output_path.mkdir(parents=True, exist_ok=True)
    settings.logs_path.mkdir(parents=True, exist_ok=True)

    try:
        drivers = sql_service.list_available_drivers()
    except Exception as exc:
        return StatusResponse(
            ok=False,
            central_reachable=False,
            message=str(exc),
            driver=settings.odbc_driver,
            output_root=str(settings.output_path),
        )

    reachable, msg = sql_service.test_central(settings)
    return StatusResponse(
        ok=reachable,
        central_reachable=reachable,
        message=msg,
        driver=settings.resolve_driver(),
        output_root=str(settings.output_path),
        details={
            "drivers": drivers,
            "sp": [settings.sp_param_1, settings.sp_param_2],
            "server": settings.central_server,
            "database": settings.central_database,
            "user": settings.central_user,
            "sql_backend": settings.sql_backend,
            "nolock": True,
        },
    )


@app.post("/api/search", response_model=SearchResponse)
def search(payload: SearchRequest):
    settings = get_settings()
    if payload.desde > payload.hasta:
        raise HTTPException(400, "La fecha Desde no puede ser mayor que Hasta")

    try:
        rows, errors, ok, fail = sql_service.search_all_branches(
            settings, payload.desde, payload.hasta
        )
    except Exception as exc:
        logger.exception("search failed")
        raise HTTPException(502, f"Error consultando SQL: {exc}") from exc

    return SearchResponse(
        total=len(rows),
        rows=rows,
        branches_ok=ok,
        branches_error=fail,
        errors=errors,
        demo=False,
    )


@app.post("/api/generate-download")
def generate_download(payload: GenerateRequest):
    if not payload.rows:
        raise HTTPException(400, "No hay registros para generar el TXT")

    filename = output_filename(payload.hasta)
    content = build_ibper_bytes(payload.rows)
    return Response(
        content=content,
        media_type="text/plain; charset=iso-8859-1",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-IBPER-Filename": filename,
            "X-IBPER-Lines": str(len(payload.rows)),
        },
    )


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

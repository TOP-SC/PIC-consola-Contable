"""Punto de entrada local y para el ejecutable portable."""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _prepare_paths() -> None:
    # En desarrollo: backend en sys.path
    here = Path(__file__).resolve().parent
    backend = here / "backend"
    if backend.exists() and str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    # En build frozen, PyInstaller ya incluye los módulos
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", here))
        if str(meipass) not in sys.path:
            sys.path.insert(0, str(meipass))


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _cfg(env_file: dict[str, str], key: str, default: str) -> str:
    return os.environ.get(key, env_file.get(key, default)).strip()


def main() -> None:
    _prepare_paths()

    import uvicorn
    from config import app_dir, resource_dir

    # Asegurar carpetas de trabajo junto al exe / app
    root = app_dir()
    (root / "Documentos").mkdir(parents=True, exist_ok=True)
    (root / "Logs").mkdir(parents=True, exist_ok=True)

    # Copiar .env de ejemplo si falta
    env_path = root / ".env"
    example = root / ".env.example"
    if not env_path.exists() and example.exists():
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    dotenv = _load_dotenv(env_path)
    host = _cfg(dotenv, "ARBA_HOST", "127.0.0.1") or "127.0.0.1"
    port = int(_cfg(dotenv, "ARBA_PORT", "8787") or "8787")
    no_browser = _cfg(dotenv, "ARBA_NO_BROWSER", "0").lower() in {"1", "true", "yes"}
    public_url = _cfg(dotenv, "ARBA_PUBLIC_URL", "") or f"http://{host}:{port}"

    def _open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass

    if not no_browser:
        threading.Thread(target=_open_browser, daemon=True).start()

    print(f"ARBA IBPER Contable")
    print(f"Escuchando: {host}:{port}")
    print(f"URL local: http://127.0.0.1:{port}")
    if public_url:
        print(f"URL red:  {public_url}")
    print(f"Carpeta: {root}")
    print(f"Recursos: {resource_dir()}")
    print("Ctrl+C para salir")

    # Importar app después de preparar paths
    from main import app  # noqa: WPS433

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

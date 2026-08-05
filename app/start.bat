@echo off
cd /d "%~dp0"

REM Si el venv apunta a otro equipo / Python roto, lo regenera
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
  if errorlevel 1 (
    echo El entorno virtual esta roto. Se regenera...
    rmdir /s /q ".venv"
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual con Python 3.12...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo No se encontro Python 3.12. En servidores usa la carpeta portable\ generada con build_portable.bat
    pause
    exit /b 1
  )
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo.
echo Iniciando ARBA IBPER en http://127.0.0.1:8787
".venv\Scripts\python.exe" run_server.py
pause

@echo off
cd /d "%~dp0"
echo.
echo Actualiza el RDS desde esta carpeta local.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ActualizarRDS.ps1"
echo.
pause

@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\ActualizarRDS.ps1" -LocalPath "%~dp0ARBA_IBPER"
echo.
pause

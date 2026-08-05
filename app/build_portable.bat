@echo off
cd /d "%~dp0"
echo === Build portable ARBA IBPER ===

if not exist ".venv\Scripts\python.exe" (
  echo Creando venv de build...
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)

.venv\Scripts\python.exe -m pip install pyinstaller pymssql
if errorlevel 1 (
  echo Fallo instalando PyInstaller/pymssql
  pause
  exit /b 1
)

echo Compilando...
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ARBA_IBPER.spec
if errorlevel 1 (
  echo Fallo el build
  pause
  exit /b 1
)

set OUT=portable
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"
xcopy /e /i /y "dist\ARBA_IBPER" "%OUT%\ARBA_IBPER" >nul
copy /y ".env" "%OUT%\ARBA_IBPER\.env" >nul
copy /y ".env.example" "%OUT%\ARBA_IBPER\.env.example" >nul
mkdir "%OUT%\ARBA_IBPER\Documentos" 2>nul
mkdir "%OUT%\ARBA_IBPER\Logs" 2>nul

(
echo @echo off
echo cd /d "%%~dp0"
echo start "" "ARBA_IBPER.exe"
) > "%OUT%\ARBA_IBPER\Iniciar.bat"

echo.
echo LISTO. Copia esta carpeta al servidor:
echo   %cd%\%OUT%\ARBA_IBPER
echo En el servidor solo hace falta ejecutar Iniciar.bat / ARBA_IBPER.exe
echo No requiere instalar Python.
pause

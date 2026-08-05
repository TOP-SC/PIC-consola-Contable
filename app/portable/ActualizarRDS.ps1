param(
    [string]$Rds = "10.100.3.26",
    [string]$RemotePath = "C:\Programas\Contable\app\portable\ARBA_IBPER",
    [string]$LocalPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $LocalPath) {
    $LocalPath = Join-Path $PSScriptRoot "ARBA_IBPER"
    if (-not (Test-Path (Join-Path $LocalPath "ARBA_IBPER.exe"))) {
        $LocalPath = Join-Path $PSScriptRoot "portable\ARBA_IBPER"
    }
}

$unc = "\\$Rds\C$" + ($RemotePath.Substring(2))

Write-Host ""
Write-Host "=== PIC / ARBA IBPER - Actualizar RDS ==="
Write-Host "Origen : $LocalPath"
Write-Host "Destino: $unc"
Write-Host ""

if (-not (Test-Path (Join-Path $LocalPath "ARBA_IBPER.exe"))) {
    Write-Host "ERROR: no encuentro ARBA_IBPER.exe en el origen."
    Write-Host "Ejecuta este script desde app\ o desde app\portable\"
    exit 1
}

Write-Host "1) Deteniendo app en el RDS..."
try {
    Get-WmiObject Win32_Process -ComputerName $Rds -Filter "Name='ARBA_IBPER.exe'" |
        ForEach-Object {
            Write-Host ("   Cerrando PID " + $_.ProcessId)
            [void]$_.Terminate()
        }
    Start-Sleep -Seconds 2
} catch {
    Write-Host "   No habia proceso o no se pudo consultar (sigo igual)."
}

Write-Host "2) Copiando archivos (sin tocar Documentos/Logs del RDS)..."
New-Item -ItemType Directory -Force -Path $unc | Out-Null

# /MIR sincroniza, pero excluye carpetas de trabajo del servidor
$robolog = Join-Path $env:TEMP ("pic_update_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
$args = @(
    $LocalPath,
    $unc,
    "/MIR",
    "/XD", "Documentos", "Logs",
    "/XF", "*.log",
    "/R:2", "/W:2",
    "/NFL", "/NDL", "/NP",
    "/LOG:$robolog"
)

& robocopy @args | Out-Null
$code = $LASTEXITCODE

# Robocopy: 0-7 = OK / con cambios; >=8 = error real
if ($code -ge 8) {
    Write-Host "ERROR en robocopy. Codigo=$code"
    Write-Host "Log: $robolog"
    exit $code
}

Write-Host "   Copia OK (robocopy=$code)"
Write-Host ""
Write-Host "Listo. El RDS ya tiene la version nueva."
Write-Host "Ahora podes ejecutar IniciarDesdeTR.bat para levantarla."
Write-Host ""

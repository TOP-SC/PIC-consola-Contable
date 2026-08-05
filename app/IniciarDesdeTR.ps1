param(
    [string]$Rds = "10.100.3.26",
    [string]$AppDir = "C:\Programas\Contable\app\portable\ARBA_IBPER",
    [string]$Url = "http://10.100.3.26:8787"
)

$ErrorActionPreference = "Stop"
$exe = Join-Path $AppDir "ARBA_IBPER.exe"

Write-Host ""
Write-Host "=== ARBA IBPER - Iniciador remoto ==="
Write-Host "RDS: $Rds"
Write-Host "EXE: $exe"
Write-Host ""

function Test-AppHealth {
    param([string]$TargetUrl)
    try {
        $r = Invoke-WebRequest -Uri "$TargetUrl/api/health" -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

if (Test-AppHealth -TargetUrl $Url) {
    Write-Host "La app YA esta corriendo en red."
    Start-Process $Url
    exit 0
}

Write-Host "Deteniendo instancia previa si existe..."
try {
    Get-WmiObject Win32_Process -ComputerName $Rds -Filter "Name='ARBA_IBPER.exe'" |
        ForEach-Object { [void]$_.Terminate() }
    Start-Sleep -Seconds 2
} catch {
    # si no hay proceso o no se puede, seguimos
}

# Forzamos ARBA_HOST en el entorno del proceso remoto (aunque el .exe sea viejo)
$remoteCmd = @(
    'cmd.exe /c '
    ('cd /d "{0}" && ' -f $AppDir)
    'set ARBA_HOST=0.0.0.0&& '
    'set ARBA_PORT=8787&& '
    'set ARBA_NO_BROWSER=1&& '
    ('"{0}"' -f $exe)
) -join ''

Write-Host "Iniciando en el RDS con ARBA_HOST=0.0.0.0 ..."
try {
    $result = ([wmiclass]"\\$Rds\root\cimv2:Win32_Process").Create($remoteCmd)
    if ($result.ReturnValue -ne 0) {
        throw "WMI ReturnValue=$($result.ReturnValue)"
    }
    Write-Host "OK. Proceso iniciado. PID=$($result.ProcessId)"
} catch {
    Write-Host "FALLO el inicio remoto: $($_.Exception.Message)"
    Write-Host "Ejecuta este script como administrador en el TR."
    exit 1
}

Write-Host "Esperando HTTP en red..."
$ok = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    if (Test-AppHealth -TargetUrl $Url) {
        $ok = $true
        break
    }
}

if ($ok) {
    Write-Host "Listo. Abriendo $Url"
    Start-Process $Url
    exit 0
}

Write-Host "El proceso se lanzo, pero HTTP en red no responde."
Write-Host "En el RDS ejecuta: netstat -ano | findstr 8787"
Write-Host "Tiene que decir 0.0.0.0:8787 (no 127.0.0.1:8787)"
Start-Process $Url
exit 2

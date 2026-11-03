<#
Abre el panel; si el sistema no está corriendo lo enciende y espera a que termine de cargar. Doble clic en abrir_panel.bat.
Sirve igual con el servicio de Windows (scripts\servicio.ps1) o con Docker (scripts\docker.ps1): usa el que esté instalado/corriendo.
#>
$Raiz = Split-Path -Parent $PSScriptRoot
$Panel = 'http://localhost:8000/panel'
function Responde($url) { try { (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false } }
function Vision-Lista { try { (Invoke-RestMethod -Uri 'http://127.0.0.1:8100/estado' -TimeoutSec 3).PSObject.Properties.Count -gt 0 } catch { $false } }

if (-not (Responde 'http://127.0.0.1:8000/health')) {
    $tarea = Get-ScheduledTask -TaskName 'IEST-Estacionamiento' -ErrorAction SilentlyContinue
    if ($tarea -and $tarea.State -eq 'Disabled') {
        # tarea desactivada = se usa Docker (scripts\docker.ps1): enciende Docker Desktop si hace falta y levanta los contenedores
        Write-Host 'Modo Docker: encendiendo Docker Desktop y los contenedores...'
        & (Join-Path $PSScriptRoot 'docker.ps1')
    } elseif ($tarea) {
        if ($tarea.State -ne 'Running') { Write-Host 'Encendiendo el sistema...'; Start-ScheduledTask -TaskName 'IEST-Estacionamiento' }
        else { Write-Host 'El sistema se está encendiendo (tras iniciar sesión puede tardar varios minutos)...' }
    } else {
        Write-Host 'El servicio no está instalado. Lo instalo y lo enciendo...'
        & (Join-Path $PSScriptRoot 'servicio.ps1') instalar
    }
    $t0 = Get-Date
    while (-not (Responde 'http://127.0.0.1:8000/health')) {
        $s = [int]((Get-Date) - $t0).TotalSeconds
        Write-Host ("  esperando a la API... {0} s" -f $s)
        if ($s -gt 900) { Write-Host 'Pasaron 15 minutos sin respuesta. Revisa logs\sistema.log'; Read-Host 'Enter para cerrar'; exit 1 }
        Start-Sleep -Seconds 5
    }
}
Write-Host 'La API está lista. Abriendo el panel...'
Start-Process $Panel
if (-not (Vision-Lista)) { Write-Host 'Las cámaras tardan un par de minutos más en cargar el modelo; el panel se actualiza solo.' }
Start-Sleep -Seconds 4

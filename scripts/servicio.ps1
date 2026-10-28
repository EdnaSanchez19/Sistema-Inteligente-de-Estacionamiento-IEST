<#
Deja el sistema corriendo en segundo plano en este equipo, sin ventanas y sin que nadie lo tenga que iniciar.

    scripts\servicio.ps1 instalar    # crea la tarea de Windows "IEST-Estacionamiento" (arranca al iniciar sesion) y la inicia
    scripts\servicio.ps1 estado      # esta corriendo? URL, ultimas lineas del registro
    scripts\servicio.ps1 detener     # detiene el sistema (vuelve a arrancar en el proximo inicio de sesion)
    scripts\servicio.ps1 iniciar     # lo vuelve a iniciar
    scripts\servicio.ps1 reiniciar
    scripts\servicio.ps1 quitar      # detiene el sistema y elimina la tarea

Panel: http://localhost:8000/panel . Solo se puede abrir desde este equipo (la API escucha en 127.0.0.1).
No necesita permisos de administrador: es una tarea del usuario actual. Arranca cuando ESE usuario inicia sesion en Windows
(no antes) y si el sistema se cae lo reinicia hasta 5 veces. El registro queda en logs\sistema.log.
No lo uses a la vez que "python scripts\iniciar_sistema.py": los dos usarian los mismos puertos (8000 y 8100).
#>
param([Parameter(Position = 0)][ValidateSet('instalar', 'quitar', 'iniciar', 'detener', 'reiniciar', 'estado')][string]$Accion = 'estado')

$Nombre = 'IEST-Estacionamiento'
$Raiz = Split-Path -Parent $PSScriptRoot
$Pythonw = Join-Path $Raiz '.venv\Scripts\pythonw.exe'
$Registro = Join-Path $Raiz 'logs\sistema.log'
$PidArchivo = Join-Path $Raiz 'logs\sistema.pid'
$Salud = 'http://127.0.0.1:8000/health'

function Tarea { Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue }
function Responde { try { (Invoke-WebRequest -Uri $Salud -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false } }

function Detener-Sistema {
    if (Tarea) { Stop-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue }
    if (Test-Path $PidArchivo) {
        $p = (Get-Content $PidArchivo -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($p -match '^\d+$') { & taskkill.exe /F /T /PID $p 2>$null | Out-Null }
        Remove-Item $PidArchivo -ErrorAction SilentlyContinue
    }
    # lo que haya quedado escuchando en los puertos del sistema y sea de este proyecto
    foreach ($c in (Get-NetTCPConnection -State Listen -LocalPort 8000, 8100 -ErrorAction SilentlyContinue)) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -like "*$Raiz*") { & taskkill.exe /F /T /PID $c.OwningProcess 2>$null | Out-Null }
    }
}

function Esperar-Sistema {
    Write-Host 'Esperando a que arranque (el modelo tarda de 20 a 60 s en cargar)...'
    for ($i = 0; $i -lt 90; $i++) { if (Responde) { return $true }; Start-Sleep -Seconds 2 }
    return $false
}

switch ($Accion) {
    'instalar' {
        if (-not (Test-Path $Pythonw)) { throw "No existe $Pythonw. Crea el entorno virtual (.venv) primero, ver README." }
        if (Responde) { Write-Host 'Ya hay un sistema respondiendo en el puerto 8000 (iniciado a mano?). Detenlo antes de instalar el servicio.'; exit 1 }
        $argumentos = '"' + (Join-Path $Raiz 'scripts\iniciar_sistema.py') + '" --oculto --host 127.0.0.1'
        $accion = New-ScheduledTaskAction -Execute $Pythonw -Argument $argumentos -WorkingDirectory $Raiz
        $usuario = "$env:USERDOMAIN\$env:USERNAME"
        $disparador = New-ScheduledTaskTrigger -AtLogOn -User $usuario
        $config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
        $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador -Settings $config -Principal $principal `
            -Description 'Sistema Inteligente de Estacionamiento IEST: API, vision y panel en localhost' -Force | Out-Null
        Write-Host "Tarea '$Nombre' instalada: arrancara sola cada vez que inicies sesion."
        Start-ScheduledTask -TaskName $Nombre
        if (Esperar-Sistema) { Write-Host 'Listo: http://localhost:8000/panel  (usuario y clave en credenciales.txt)' }
        else { Write-Host "No respondio a tiempo. Revisa $Registro"; exit 1 }
    }
    'iniciar' {
        if (-not (Tarea)) { throw 'El servicio no esta instalado. Usa: scripts\servicio.ps1 instalar' }
        if (Responde) { Write-Host 'Ya esta corriendo: http://localhost:8000/panel'; break }
        Start-ScheduledTask -TaskName $Nombre
        if (Esperar-Sistema) { Write-Host 'Listo: http://localhost:8000/panel' } else { Write-Host "No respondio a tiempo. Revisa $Registro"; exit 1 }
    }
    'detener' { Detener-Sistema; Write-Host 'Sistema detenido.' }
    'reiniciar' {
        Detener-Sistema; Start-Sleep -Seconds 3
        Start-ScheduledTask -TaskName $Nombre
        if (Esperar-Sistema) { Write-Host 'Listo: http://localhost:8000/panel' } else { Write-Host "No respondio a tiempo. Revisa $Registro"; exit 1 }
    }
    'quitar' {
        Detener-Sistema
        if (Tarea) { Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false; Write-Host "Tarea '$Nombre' eliminada." } else { Write-Host 'No habia tarea instalada.' }
    }
    'estado' {
        $t = Tarea
        Write-Host ("Servicio instalado : " + $(if ($t) { "si (tarea '$Nombre', estado $($t.State))" } else { 'no' }))
        Write-Host ("Responde en :8000  : " + $(if (Responde) { 'si -> http://localhost:8000/panel' } else { 'no' }))
        if (Test-Path $Registro) { Write-Host "`nUltimas lineas de $Registro :"; Get-Content $Registro -Tail 8 }
    }
}

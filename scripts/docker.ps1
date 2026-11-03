<#
Levanta el sistema completo en Docker (PostgreSQL + API con el panel + servidor de visión con GPU) con un solo comando.

    scripts\docker.ps1              # prepara las claves, enciende Docker Desktop si hace falta, construye, levanta y espera
    scripts\docker.ps1 detener      # lo detiene (los datos se conservan)
    scripts\docker.ps1 estado       # qué contenedores corren
    scripts\docker.ps1 logs         # sigue los registros
    scripts\docker.ps1 borrar       # lo detiene Y BORRA la base de datos de Docker

Panel: http://localhost:8000/panel . El usuario administrador es admin@iest.edu.mx y su clave queda en credenciales.docker.txt
(archivo local, no se sube a git). Comparte los puertos 8000 y 8100 con el servicio de Windows (scripts\servicio.ps1), así que si ese
está corriendo, este script lo detiene antes de levantar Docker.
#>
param([Parameter(Position = 0)][ValidateSet('iniciar', 'detener', 'estado', 'logs', 'borrar')][string]$Accion = 'iniciar')

# 'Continue': docker escribe su progreso por el canal de errores y PowerShell 5.1 lo tomaría por una falla; las fallas reales se revisan con $LASTEXITCODE
$ErrorActionPreference = 'Continue'
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
$Env = Join-Path $Raiz '.env'
$Credenciales = Join-Path $Raiz 'credenciales.docker.txt'

function Motor-Listo { cmd /c 'docker info >nul 2>&1'; return ($LASTEXITCODE -eq 0) }
function Responde($url) { try { (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false } }
function Clave($n) { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $n | ForEach-Object { [char]$_ }) }

function Valor-Env($nombre) {
    if (-not (Test-Path $Env)) { return $null }
    $l = Get-Content $Env -Encoding UTF8 | Where-Object { $_ -match "^$nombre=" } | Select-Object -First 1
    if ($l) { return ($l -replace "^$nombre=", '').Trim() } else { return $null }
}
function Poner-Env($nombre, $valor) {
    $lineas = if (Test-Path $Env) { @(Get-Content $Env -Encoding UTF8) } else { @() }
    $hay = $false
    $lineas = $lineas | ForEach-Object { if ($_ -match "^$nombre=") { $hay = $true; "$nombre=$valor" } else { $_ } }
    if (-not $hay) { $lineas += "$nombre=$valor" }
    Set-Content -Path $Env -Value $lineas -Encoding UTF8
}

if ($Accion -eq 'estado') { if (Motor-Listo) { docker compose ps } else { Write-Host 'Docker Desktop no está encendido.' }; return }
if ($Accion -eq 'logs') { docker compose logs -f --tail 50; return }
if ($Accion -eq 'detener') { docker compose stop; Write-Host 'Detenido. Para volver a levantarlo: scripts\docker.ps1'; return }
if ($Accion -eq 'borrar') {
    Write-Host 'Esto BORRA la base de datos de Docker (usuarios, eventos, estados). El servicio de Windows tiene su propia base y no se toca.'
    if ((Read-Host 'Escribe BORRAR para confirmar') -ne 'BORRAR') { Write-Host 'Cancelado.'; return }
    docker compose down -v; return
}

# --- 1. claves: se crean una vez y se conservan -------------------------------------------------------------------------------
if (-not (Test-Path $Env)) { Copy-Item (Join-Path $Raiz '.env.example') $Env }
foreach ($par in @(@('POSTGRES_PASSWORD', 18), @('JWT_SECRET', 48), @('INGEST_API_KEY', 32))) {
    $v = Valor-Env $par[0]
    if (-not $v -or $v -like 'cambia_*') { Poner-Env $par[0] (Clave $par[1]) }
}
$admin = Valor-Env 'SEED_ADMIN_PASSWORD'
if (-not $admin) {
    $admin = Clave 16
    Poner-Env 'SEED_ADMIN_PASSWORD' $admin
    Set-Content -Path $Credenciales -Value "Acceso al panel en Docker (archivo local, no se sube a git)`r`n`r`nAdministrador: admin@iest.edu.mx / $admin" -Encoding UTF8
}

# --- 2. lo que Docker no lleva dentro de la imagen ----------------------------------------------------------------------------
$faltan = @('real_a.mp4', 'real_b.mp4', 'real_c.mp4') | Where-Object { -not (Test-Path (Join-Path $Raiz "datasets\reales\$_")) }
if ($faltan) { throw "Faltan los videos de las cámaras en datasets\reales\: $($faltan -join ', ')" }
foreach ($m in 'yolov8n.pt', 'yolov8s.pt') { if (-not (Test-Path (Join-Path $Raiz "vision\models\$m"))) { throw "Falta vision\models\$m (ver docs\EJECUCION.md)" } }

# --- 3. puertos: el servicio de Windows usa los mismos -------------------------------------------------------------------------
if (Get-NetTCPConnection -State Listen -LocalPort 8000, 8100 -ErrorAction SilentlyContinue) {
    Write-Host 'Hay algo usando los puertos 8000/8100 (el servicio de Windows). Lo detengo para usar Docker...'
    # la tarea se reinicia sola si se cae: hay que desactivarla, o un minuto después volvería a ocupar los puertos
    Disable-ScheduledTask -TaskName 'IEST-Estacionamiento' -ErrorAction SilentlyContinue | Out-Null
    # en un proceso aparte: así sus avisos de taskkill no cuentan como errores de este script
    Start-Process -FilePath powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'servicio.ps1'), 'detener' -Wait -WindowStyle Hidden
    Start-Sleep -Seconds 5
    if (Get-NetTCPConnection -State Listen -LocalPort 8000, 8100 -ErrorAction SilentlyContinue) { throw 'Los puertos 8000/8100 siguen ocupados por otro programa. Ciérralo y vuelve a intentar.' }
}

# --- 4. motor de Docker ---------------------------------------------------------------------------------------------------------
if (-not (Motor-Listo)) {
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $exe)) { throw 'No encuentro Docker Desktop. Instálalo desde https://www.docker.com/products/docker-desktop/' }
    Write-Host 'Encendiendo Docker Desktop (puede tardar un par de minutos)...'
    Start-Process $exe
    for ($i = 0; $i -lt 90 -and -not (Motor-Listo); $i++) { Start-Sleep -Seconds 4 }
    if (-not (Motor-Listo)) { throw 'Docker Desktop no terminó de encender. Ábrelo a mano y vuelve a correr este script.' }
}

# --- 5. construir y levantar -----------------------------------------------------------------------------------------------------
Write-Host 'Construyendo y levantando (la primera vez baja varios GB: la imagen de visión pesa unos 8 GB)...'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'docker compose falló. Revisa el mensaje de arriba.' }
Write-Host 'Esperando a la API...'
for ($i = 0; $i -lt 100 -and -not (Responde 'http://127.0.0.1:8000/health'); $i++) { Start-Sleep -Seconds 3 }
if (-not (Responde 'http://127.0.0.1:8000/health')) { Write-Host 'La API no respondió a tiempo. Mira: scripts\docker.ps1 logs'; exit 1 }
Write-Host "Listo: http://localhost:8000/panel  (usuario y clave en credenciales.docker.txt)"
Write-Host 'El servidor de visión tarda un par de minutos más en cargar los modelos; el panel lo muestra solo.'

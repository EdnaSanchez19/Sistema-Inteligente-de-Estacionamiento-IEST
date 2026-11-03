# Docker

El sistema completo en contenedores: **PostgreSQL**, la **API con el panel** y el **servidor de visión con GPU**.

```powershell
scripts\docker.ps1
```

Un solo comando. La primera vez:
1. Crea las claves en `.env` (contraseña de la base, secreto del login, clave de ingesta) y la del administrador en `credenciales.docker.txt`.
2. Si el servicio de Windows está corriendo, lo detiene (comparten los puertos 8000 y 8100).
3. Enciende Docker Desktop si estaba apagado.
4. Construye las imágenes (la de visión pesa unos 8 GB: lleva PyTorch con CUDA) y levanta todo.

Panel: `http://localhost:8000/panel` · usuario `admin@iest.edu.mx`, clave en `credenciales.docker.txt`. El servidor de visión tarda un par de
minutos más en cargar los modelos; el panel lo muestra solo.

| Comando | Para qué |
|---|---|
| `scripts\docker.ps1` | Preparar y levantar (también sirve para volver a levantarlo) |
| `scripts\docker.ps1 estado` | Qué contenedores corren |
| `scripts\docker.ps1 logs` | Seguir los registros |
| `scripts\docker.ps1 detener` | Detenerlo (la base de datos se conserva) |
| `scripts\docker.ps1 borrar` | Detenerlo y **borrar la base de datos de Docker** (pide confirmación) |

## Qué hay dentro y qué se monta desde fuera
- **Dentro de las imágenes:** solo el código (`api/app`, `vision/parking_vision`) y sus dependencias.
- **Se montan desde el disco (solo lectura):** los videos de las cámaras (`datasets/reales/`, pesan 210 MB y llevan personas y placas: no se
  meten en la imagen ni en Git), los modelos (`vision/models/*.pt`) y la configuración de las cámaras (`camaras/`).
- **Datos:** PostgreSQL guarda todo en el volumen `pgdata`. La base de Docker es **independiente** de la del servicio de Windows (`api/dev.db`): no
  comparten usuarios, eventos ni estados.
- **Red:** los puertos solo se abren en este equipo (`127.0.0.1`): 8000 (API y panel), 8100 (video de las cámaras) y 5432 (PostgreSQL).

## Requisitos
- Windows con **Docker Desktop** (motor WSL2) y una **GPU NVIDIA** con su controlador al día. Sin GPU, quita el bloque `deploy:` del servicio
  `vision` en `docker-compose.yml`: funciona en CPU, pero con dos modelos cada ciclo tarda muchos segundos.
- Los 3 videos en `datasets/reales/` y `yolov8n.pt` y `yolov8s.pt` en `vision/models/`.

## Servicio de Windows o Docker
**`scripts\docker.ps1` desactiva el inicio automático del servicio de Windows** (si no, la tarea se reinicia sola y vuelve a ocupar los puertos). Para volver al servicio:
`scripts\docker.ps1 detener` y luego `scripts\servicio.ps1 iniciar` (lo reactiva). El acceso directo del Escritorio (`scriptsbrir_panel.bat`) funciona en los dos modos: en modo
Docker enciende Docker Desktop y los contenedores si estaban apagados. Docker Desktop **no** arranca solo al iniciar sesión (Settings → General → *Start Docker Desktop when you sign in* lo activa).

Hacen lo mismo y **no pueden correr a la vez**. El servicio de Windows (`scripts\servicio.ps1`) arranca solo al iniciar sesión; Docker se
levanta con `scripts\docker.ps1` (y con `restart: unless-stopped` vuelve solo si Docker Desktop está abierto). Docker sirve para llevar el sistema a
otro equipo o a un servidor sin instalar Python ni dependencias.

## Notas
- La API crea las tablas y carga los 391 cajones, las cámaras y el administrador en cada arranque (es idempotente).
- Usar PostgreSQL en lugar de SQLite es nuevo: la migración de bases viejas (`db/migraciones/`) no se ha probado contra un PostgreSQL con datos reales.

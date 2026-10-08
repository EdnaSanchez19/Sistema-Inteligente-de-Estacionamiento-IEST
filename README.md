# Sistema Inteligente de Estacionamiento — IEST Anáhuac

Detecta en tiempo real qué cajones del estacionamiento están libres u ocupados a partir de las
cámaras de videovigilancia (RTSP), identifica el colgante del vehículo y expone la información
mediante una API y una app móvil.

```
Cámaras ──RTSP/LAN──▶ vision/ (YOLOv8 + OpenCV) ──▶ api/ (FastAPI) ──▶ PostgreSQL
                                                         ▲
                                                  mobile/ (React Native)
```

| Carpeta | Contenido | Tarea del cronograma |
|---|---|---|
| `mobile/` | App móvil React Native (Expo) | 3.1 |
| `api/`, `docker-compose.yml`, `scripts/` | Entorno, servidor y API | 3.2 |
| `db/`, `api/app/models.py` | Modelo y esquema de base de datos | 3.3 |
| `vision/` | Servidor de procesamiento de imagen | 3.4 |

## Requisitos

- Python 3.10+ (probado en 3.12)
- Node.js 20+ (solo para la app móvil)
- Docker (para PostgreSQL y la API)
- GPU NVIDIA opcional: acelera YOLO, pero no es necesaria con `yolov8n`

## Puesta en marcha del entorno (tarea 3.2)

```bash
cp .env.example .env              # y cambia las contraseñas
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install -r api/requirements.txt -r vision/requirements.txt
python scripts/check_env.py       # verifica OpenCV, YOLO, torch, docker, node...
docker compose up -d db api       # PostgreSQL + API en http://localhost:8000/docs
```

## Flujo de trabajo

- Una rama `main` estable; cada tarea del cronograma entra como un commit/PR `feat(X.Y): ...`.
- Los secretos van en `.env` (ignorado por git). Nunca se suben contraseñas ni modelos `.pt`.
- Los fotogramas de las cámaras se procesan en memoria y no se guardan, salvo el modo opcional
  de recolección de baja confianza para reentrenamiento (desactivado por defecto).

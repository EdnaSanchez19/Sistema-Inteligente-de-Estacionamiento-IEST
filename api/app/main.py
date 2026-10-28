import asyncio
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import get_settings
from .db import Base, SessionLocal, engine, migrar_esquema
from .routers import admin, auth, consulta, ingest, sistema
from .watchdog import muestrear, vigilar


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # en el piloto; si el esquema crece, migrar a Alembic
    migrar_esquema()
    tareas = [asyncio.create_task(vigilar(SessionLocal)), asyncio.create_task(muestrear(SessionLocal))]
    yield
    for t in tareas:
        t.cancel()


app = FastAPI(title="Estacionamiento IEST API", version="1.0.0", lifespan=lifespan)

# CORS solo para los orígenes configurados (la app en el navegador). Sin cookies: el token va en el encabezado.
_origenes = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
if _origenes:
    app.add_middleware(CORSMiddleware, allow_origins=_origenes, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(consulta.router)
app.include_router(admin.router)
app.include_router(ingest.router)
app.include_router(sistema.router)


@app.get("/panel", include_in_schema=False)
def panel() -> FileResponse:
    """Panel web de una sola página con la disponibilidad en vivo (para demostraciones)."""
    return FileResponse(Path(__file__).parent / "static" / "panel.html", media_type="text/html")


@app.get("/panel/portada.jpg", include_in_schema=False)
def portada() -> FileResponse:
    """Foto de la pantalla de inicio de sesión del panel."""
    return FileResponse(Path(__file__).parent / "static" / "portada.jpg", media_type="image/jpeg")


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"status": "ok"}

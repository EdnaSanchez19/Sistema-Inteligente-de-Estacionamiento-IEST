import asyncio
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from .config import get_settings
from .db import Base, SessionLocal, engine, migrar_esquema
from .routers import admin, alertas, auth, consulta, ingest, reportes, sistema
from .watchdog import mantener, muestrear, vigilar


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # en el piloto; si el esquema crece, migrar a Alembic
    migrar_esquema()
    tareas = [asyncio.create_task(vigilar(SessionLocal)), asyncio.create_task(muestrear(SessionLocal)), asyncio.create_task(mantener(SessionLocal))]
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
app.include_router(alertas.router)
app.include_router(reportes.router)


_ESTATICOS = Path(__file__).parent / "static"


class _SinCache(StaticFiles):
    """Archivos del panel con revalidación: un cambio se ve al recargar, sin forzar la recarga."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


@app.get("/panel", include_in_schema=False)
def panel() -> FileResponse:
    """Panel web (operación y administración). Es estático: los datos los pide a esta misma API con el token del usuario."""
    return FileResponse(_ESTATICOS / "panel" / "index.html", media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/panel/portada.jpg", include_in_schema=False)
def portada() -> FileResponse:
    """Foto de la pantalla de inicio de sesión del panel."""
    return FileResponse(_ESTATICOS / "portada.jpg", media_type="image/jpeg")


app.mount("/panel", _SinCache(directory=_ESTATICOS / "panel"), name="panel")  # css/ y js/ del panel


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"status": "ok"}

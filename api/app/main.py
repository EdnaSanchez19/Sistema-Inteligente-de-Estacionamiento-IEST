import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, SessionLocal, engine
from .routers import admin, auth, consulta, ingest
from .watchdog import vigilar


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # en el piloto; si el esquema crece, migrar a Alembic
    tarea = asyncio.create_task(vigilar(SessionLocal))
    yield
    tarea.cancel()


app = FastAPI(title="Estacionamiento IEST API", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(consulta.router)
app.include_router(admin.router)
app.include_router(ingest.router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"status": "ok"}

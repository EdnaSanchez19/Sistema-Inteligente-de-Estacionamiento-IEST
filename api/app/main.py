from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .routers import auth, consulta, ingest


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # en el piloto; si el esquema crece, migrar a Alembic
    yield


app = FastAPI(title="Estacionamiento IEST API", version="0.2.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(consulta.router)
app.include_router(ingest.router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"status": "ok"}

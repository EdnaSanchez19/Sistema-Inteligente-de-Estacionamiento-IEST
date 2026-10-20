import os

# Antes de importar la app: configuración de pruebas (BD en memoria y secretos de prueba).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-longitud-suficiente"
os.environ["INGEST_API_KEY"] = "clave-ingesta-pruebas"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import seed  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "demo-pass-123")
    # StaticPool: una sola conexión en memoria compartida por toda la prueba
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed.seed_base(s)
        seed.seed_demo(s)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()

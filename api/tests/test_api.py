import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import seed
from app.db import Base, get_db
from app.main import app
from app.models import Espacio, EstadoEspacio

KEY = {"X-API-Key": "clave-ingesta-pruebas"}


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


def login(client, correo, password):
    r = client.post("/auth/login", data={"username": correo, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None


def test_login_y_me(client):
    assert client.post("/auth/login", data={"username": "demo@iest.edu.mx", "password": "mala"}).status_code == 401
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    me = client.get("/auth/me", headers=h).json()
    assert me["correo"] == "demo@iest.edu.mx" and me["rol"] == "estudiante"
    assert client.get("/auth/me").status_code == 401


def test_roles_en_endpoints_de_admin(client):
    demo = login(client, "demo@iest.edu.mx", "demo-pass-123")
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    assert client.get("/eventos", headers=demo).status_code == 403
    assert client.get("/eventos", headers=admin).status_code == 200
    assert client.get("/camaras", headers=demo).status_code == 403


def test_consultas_de_la_app(client):
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    espacios = client.get("/espacios", headers=h).json()
    assert len(espacios) == 48 and {"id", "numero", "zona", "tipo", "estado"} <= espacios[0].keys()
    assert len(client.get("/espacios?zona=C", headers=h).json()) == 12
    v = client.get("/vehiculos/mios", headers=h).json()
    assert v[0]["colgante"]["codigo"] == "IEST-004512"


def test_ingesta_requiere_api_key(client):
    body = {"camara": "CAM-01", "espacios": []}
    assert client.post("/ingest/ocupacion", json=body).status_code == 401
    assert client.post("/ingest/ocupacion", json=body, headers={"X-API-Key": "otra"}).status_code == 401
    assert client.post("/ingest/ocupacion", json=body, headers=KEY).status_code == 200


def test_ocupacion_genera_estado_y_eventos(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    body = {"camara": "CAM-01", "espacios": [{"numero": "A-05", "ocupado": True, "confianza": 0.91, "colgante_codigo": "IEST-004512"}, {"numero": "Z-99", "ocupado": True}]}
    r = client.post("/ingest/ocupacion", json=body, headers=KEY).json()
    assert r == {"actualizados": 1, "desconocidos": ["Z-99"]}
    estados = {e["numero"]: e["estado"] for e in client.get("/espacios", headers=admin).json()}
    assert estados["A-05"] == "ocupado"
    # repetir el mismo estado no genera eventos nuevos
    assert client.post("/ingest/ocupacion", json=body, headers=KEY).json()["actualizados"] == 0
    # salida
    body["espacios"] = [{"numero": "A-05", "ocupado": False}]
    client.post("/ingest/ocupacion", json=body, headers=KEY)
    tipos = [e["tipo"] for e in client.get("/eventos", headers=admin).json()]
    assert tipos.count("entrada") == 1 and tipos.count("salida") == 1
    descripciones = " ".join(e["descripcion"] for e in client.get("/eventos", headers=admin).json())
    assert "IEST-004512" in descripciones


def test_colgante_no_registrado_y_sin_colgante(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-06", "ocupado": True, "colgante_codigo": "FAKE-000"}, {"numero": "A-07", "ocupado": True}]})
    desc = [e["descripcion"] for e in client.get("/eventos", headers=admin).json()]
    assert any("FAKE-000 no registrado" in d for d in desc)
    assert any("sin colgante identificado" in d for d in desc)


def test_no_pisa_espacios_reservados_ni_fuera_de_servicio(client):
    db = next(app.dependency_overrides[get_db]())
    esp = db.scalar(select(Espacio).where(Espacio.numero == "A-08"))
    esp.estado = EstadoEspacio.reservado
    db.commit()
    assert client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-08", "ocupado": True}]}).json()["actualizados"] == 0


def test_camara_desconectada_y_restablecida(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    assert client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-02", "en_linea": True}).json()["estado"] == "en_linea"
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-02", "en_linea": False})
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-02", "en_linea": False})  # repetido: un solo evento
    cams = {c["camara"]: c["estado"] for c in client.get("/camaras", headers=admin).json()}
    assert cams["CAM-02"] == "desconectada"
    tipos = [e["tipo"] for e in client.get("/eventos", headers=admin).json()]
    assert tipos.count("camara_desconectada") == 1
    assert client.post("/ingest/camara-estado", headers=KEY, json={"camara": "NOPE", "en_linea": True}).status_code == 404


def test_secretos_sin_configurar_rechazan(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("INGEST_API_KEY", "cambia_esta_clave")
    get_settings.cache_clear()
    try:
        assert client.post("/ingest/ocupacion", headers={"X-API-Key": "cambia_esta_clave"}, json={"camara": "CAM-01", "espacios": []}).status_code == 503
    finally:
        monkeypatch.setenv("INGEST_API_KEY", "clave-ingesta-pruebas")
        get_settings.cache_clear()

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import Camara, EstadoCamara, Notificacion
from app.watchdog import revisar_camaras
from helpers import ADMIN, DEMO, KEY, login


def admin_headers(client):
    return login(client, *ADMIN)


def test_endpoints_de_administracion_exigen_admin(client):
    demo = login(client, *DEMO)
    for method, url in [("get", "/usuarios"), ("post", "/usuarios"), ("get", "/vehiculos"), ("get", "/colgantes"), ("patch", "/espacios/1"), ("post", "/notificaciones")]:
        assert getattr(client, method)(url, headers=demo).status_code == 403, url
        assert getattr(client, method)(url).status_code == 401, url


def test_alta_de_usuario_vehiculo_y_colgante(client):
    h = admin_headers(client)
    r = client.post("/usuarios", headers=h, json={"nombre": "Ana Docente", "correo": "Ana@IEST.edu.mx", "password": "clave-segura-1", "rol": "docente"})
    assert r.status_code == 201 and r.json()["correo"] == "ana@iest.edu.mx"
    uid = r.json()["id"]
    assert client.post("/usuarios", headers=h, json={"nombre": "Otra", "correo": "ana@iest.edu.mx", "password": "clave-segura-1"}).status_code == 409
    assert client.post("/usuarios", headers=h, json={"nombre": "X", "correo": "x@iest.edu.mx", "password": "corta"}).status_code == 422

    v = client.post("/vehiculos", headers=h, json={"usuario_id": uid, "placa": "xyz-987", "marca": "Mazda", "modelo": "3", "color": "Rojo"})
    assert v.status_code == 201 and v.json()["placa"] == "XYZ-987"
    c = client.post("/colgantes", headers=h, json={"codigo": "iest-009999", "tipo": "docente", "vehiculo_id": v.json()["id"]})
    assert c.status_code == 201 and c.json()["codigo"] == "IEST-009999"
    # un vehículo no puede tener dos colgantes
    assert client.post("/colgantes", headers=h, json={"codigo": "IEST-000001", "tipo": "docente", "vehiculo_id": v.json()["id"]}).status_code == 409

    # el usuario nuevo ya puede entrar y ve su vehículo con colgante
    nuevo = login(client, "ana@iest.edu.mx", "clave-segura-1")
    assert client.get("/vehiculos/mios", headers=nuevo).json()[0]["colgante"]["codigo"] == "IEST-009999"


def test_desactivar_usuario_bloquea_login_y_no_puede_hacerse_a_si_mismo(client):
    h = admin_headers(client)
    me = client.get("/auth/me", headers=h).json()
    assert client.patch(f"/usuarios/{me['id']}", headers=h, json={"activo": False}).status_code == 400
    demo = client.get("/auth/me", headers=login(client, *DEMO)).json()
    assert client.patch(f"/usuarios/{demo['id']}", headers=h, json={"activo": False}).status_code == 200
    assert login(client, *DEMO) is None


def test_asignar_espacio_y_correccion_manual(client):
    h = admin_headers(client)
    demo_h = login(client, *DEMO)
    demo = client.get("/auth/me", headers=demo_h).json()
    espacio = next(e for e in client.get("/espacios", headers=h).json() if e["numero"] == "A-03")

    r = client.patch(f"/espacios/{espacio['id']}", headers=h, json={"usuario_asignado_id": demo["id"], "estado": "reservado"})
    assert r.status_code == 200 and r.json()["estado"] == "reservado"
    assert client.get("/auth/me", headers=demo_h).json()["espacioAsignado"] == "A-03"
    eventos = client.get("/eventos", headers=h).json()
    assert any(e["tipo"] == "cambio_ocupacion" and "A-03" in e["descripcion"] for e in eventos)

    # desasignar con null explícito
    client.patch(f"/espacios/{espacio['id']}", headers=h, json={"usuario_asignado_id": None})
    assert client.get("/auth/me", headers=demo_h).json()["espacioAsignado"] is None
    assert client.patch("/espacios/99999", headers=h, json={"estado": "libre"}).status_code == 404


def test_aviso_manual_y_visibilidad(client):
    h = admin_headers(client)
    demo_h = login(client, *DEMO)
    demo = client.get("/auth/me", headers=demo_h).json()
    client.post("/notificaciones", headers=h, json={"titulo": "Para todos", "mensaje": "Mantenimiento zona B"})
    client.post("/notificaciones", headers=h, json={"titulo": "Solo admin", "mensaje": "privado", "usuario_id": client.get("/auth/me", headers=h).json()["id"]})
    titulos = [n["titulo"] for n in client.get("/notificaciones", headers=demo_h).json()]
    assert "Para todos" in titulos and "Solo admin" not in titulos
    assert demo["id"]  # el usuario demo existe y solo ve los suyos + los generales


def test_aviso_automatico_isla_casi_llena_y_llena(client):
    h = admin_headers(client)

    def ocupar(numeros, ocupado=True):
        return client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": ocupado} for n in numeros]})

    isla_c = [f"C-{i:02d}" for i in range(1, 37)]  # 36 cajones
    ocupar(isla_c, ocupado=False)  # la cámara observa los 36 (estado inicial: libres); hasta aquí no hay aviso posible
    ocupar(isla_c[:32])  # quedan 4 libres: aún sin aviso
    assert not [n for n in client.get("/notificaciones", headers=h).json() if "casi llena" in n["titulo"]]
    ocupar(isla_c[32:33])  # quedan 3 -> casi llena
    ocupar(isla_c[33:34])  # quedan 2 -> no repite el aviso
    avisos = [n["titulo"] for n in client.get("/notificaciones", headers=h).json()]
    assert avisos.count("Isla C casi llena") == 1
    ocupar(isla_c[34:])  # 0 libres -> llena
    assert "Isla C llena" in [n["titulo"] for n in client.get("/notificaciones", headers=h).json()]


def test_fechas_salen_con_zona_horaria_utc(client):
    h = admin_headers(client)
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-01", "en_linea": True})
    ultima = next(c for c in client.get("/camaras", headers=h).json() if c["camara"] == "CAM-01")["ultimaSenal"]
    assert ultima.endswith("Z") or ultima.endswith("+00:00")


def test_watchdog_marca_camaras_sin_senal(client):
    h = admin_headers(client)
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-01", "en_linea": True})
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-02", "en_linea": True})
    db = next(app.dependency_overrides[get_db]())
    ahora = datetime.now(timezone.utc)
    assert revisar_camaras(db, timeout_s=180, ahora=ahora) == []  # recién reportaron
    cam1 = db.scalar(select(Camara).where(Camara.codigo == "CAM-01"))
    cam1.ultima_senal = ahora - timedelta(seconds=600)
    db.commit()
    assert revisar_camaras(db, timeout_s=180, ahora=ahora) == ["CAM-01"]
    assert revisar_camaras(db, timeout_s=180, ahora=ahora) == []  # no repite el evento
    estados = {c["camara"]: c["estado"] for c in client.get("/camaras", headers=h).json()}
    assert estados["CAM-01"] == "desconectada" and estados["CAM-02"] == "en_linea"
    tipos = [e["tipo"] for e in client.get("/eventos", headers=h).json()]
    assert tipos.count("camara_desconectada") == 1


def test_no_hay_aviso_de_isla_llena_si_la_camara_no_cubre_toda_la_isla(client):
    h = admin_headers(client)
    parcial = [f"C-{i:02d}" for i in range(1, 11)]  # la cámara solo vigila 10 de los 36 cajones
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": False} for n in parcial]})
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": True} for n in parcial]})
    assert not [n for n in client.get("/notificaciones", headers=h).json() if "llena" in n["titulo"]]  # "llena" sería falso: hay 30 sin observar

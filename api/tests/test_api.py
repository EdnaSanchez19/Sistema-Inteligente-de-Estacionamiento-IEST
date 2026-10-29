from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import Espacio, EstadoEspacio
from helpers import KEY, login


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
    assert len(espacios) == 391 and {"id", "numero", "zona", "tipo", "estado", "monitoreado"} <= espacios[0].keys()
    assert not any(e["monitoreado"] for e in espacios)  # ninguna cámara ha reportado nada todavía
    assert len(client.get("/espacios?zona=C", headers=h).json()) == 36
    v = client.get("/vehiculos/mios", headers=h).json()
    assert v[0]["colgante"]["codigo"] == "IEST-004512"


def test_ingesta_requiere_api_key(client):
    body = {"camara": "CAM-01", "espacios": []}
    assert client.post("/ingest/ocupacion", json=body).status_code == 401
    assert client.post("/ingest/ocupacion", json=body, headers={"X-API-Key": "otra"}).status_code == 401
    assert client.post("/ingest/ocupacion", json=body, headers=KEY).status_code == 200


def establecer(client, camara, numeros, ocupado=False):
    """Primera observación de unos cajones: fija su estado inicial (no genera eventos)."""
    r = client.post("/ingest/ocupacion", headers=KEY, json={"camara": camara, "espacios": [{"numero": n, "ocupado": ocupado} for n in numeros]})
    assert r.status_code == 200
    return r.json()


def test_la_primera_observacion_fija_el_estado_inicial_sin_generar_eventos(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    assert establecer(client, "CAM-01", ["A-01", "A-02"], ocupado=True)["actualizados"] == 0  # no son entradas: el auto ya estaba ahí
    espacios = {e["numero"]: e for e in client.get("/espacios", headers=admin).json()}
    assert espacios["A-01"]["monitoreado"] and espacios["A-01"]["estado"] == "ocupado"
    assert not espacios["A-03"]["monitoreado"]  # nadie lo ha observado: su "libre" es solo el valor inicial
    assert not [e for e in client.get("/eventos", headers=admin).json() if e["tipo"] in ("entrada", "salida")]


def test_ocupacion_genera_estado_y_eventos(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    establecer(client, "CAM-01", ["A-05"])  # estado inicial: libre
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
    establecer(client, "CAM-01", ["A-06", "A-07"])
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


def test_cors_solo_permite_los_origenes_configurados(client):
    ok = client.options("/espacios", headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:8081"
    ajeno = client.options("/espacios", headers={"Origin": "http://sitio-ajeno.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in ajeno.headers


def test_panel_web_se_sirve_sin_autenticacion(client):
    r = client.get("/panel")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Estacionamiento IEST" in r.text


def test_detalle_de_un_cajon_solo_muestra_auditoria_a_administradores(client):
    admin, demo = login(client, "admin@iest.edu.mx", "admin-pass-123"), login(client, "demo@iest.edu.mx", "demo-pass-123")
    establecer(client, "CAM-01", ["A-09"])
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-09", "ocupado": True, "colgante_codigo": "IEST-004512"}]})
    d = client.get("/espacios/A-09", headers=admin).json()
    assert d["estado"] == "ocupado" and d["camara"] == "CAM-01" and d["monitoreado"] is True
    assert d["colgante"]["codigo"] == "IEST-004512" and d["historial"][0]["tipo"] == "entrada"
    u = client.get("/espacios/A-09", headers=demo).json()
    assert u["estado"] == "ocupado" and u["colgante"] is None and u["historial"] == []  # un usuario no ve quién estaciona
    assert client.get("/espacios/Z-99", headers=admin).status_code == 404
    assert client.get("/espacios/A-09").status_code == 401


def test_el_estado_del_sistema_cuenta_solo_cajones_monitoreados(client):
    from app import historial

    historial.limpiar()
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    e = client.get("/sistema/estado", headers=h).json()["espacios"]
    assert e["total"] == 391 and e["monitoreados"] == 0 and e["sin_monitoreo"] == 391 and e["libre"] == 0 and e["ocupado"] == 0
    establecer(client, "CAM-01", [f"A-{i:02d}" for i in range(1, 11)])
    establecer(client, "CAM-01", ["A-01", "A-02", "A-03"], ocupado=True)  # ya observados: pasan a ocupado
    e = client.get("/sistema/estado", headers=h).json()["espacios"]
    assert e["monitoreados"] == 10 and e["ocupado"] == 3 and e["libre"] == 7 and e["sin_monitoreo"] == 381


def test_la_serie_de_ocupacion_se_muestrea_y_se_consulta(client):
    from app import historial
    from app.watchdog import muestrear_ocupacion

    historial.limpiar()
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    establecer(client, "CAM-01", ["A-01", "A-02"])
    establecer(client, "CAM-01", ["A-02"], ocupado=True)
    db = next(app.dependency_overrides[get_db]())
    muestrear_ocupacion(db)
    serie = client.get("/sistema/historial?minutos=5", headers=h).json()
    assert serie[-1]["monitoreados"] == 2 and serie[-1]["ocupados"] == 1 and serie[-1]["libres"] == 1
    assert client.get("/sistema/historial?minutos=0", headers=h).status_code == 422
    historial.limpiar()


def test_una_base_antigua_sin_la_columna_monitoreado_se_migra():
    from sqlalchemy import create_engine, inspect, text

    from app.db import migrar_esquema

    eng = create_engine("sqlite://")
    with eng.begin() as con:
        con.execute(text("CREATE TABLE espacios (id INTEGER PRIMARY KEY, numero VARCHAR(20))"))
        con.execute(text("INSERT INTO espacios (numero) VALUES ('A-01')"))
    migrar_esquema(eng)
    migrar_esquema(eng)  # idempotente
    assert "monitoreado" in {c["name"] for c in inspect(eng).get_columns("espacios")}
    with eng.connect() as con:
        assert con.execute(text("SELECT monitoreado FROM espacios")).scalar() in (0, False)  # lo existente queda como "sin monitoreo"


def test_en_calentamiento_los_cambios_son_estado_inicial_no_entradas_ni_salidas(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    establecer(client, "CAM-01", ["A-01", "A-02"])  # libres
    r = client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "calentamiento": True, "espacios": [{"numero": "A-01", "ocupado": True}]}).json()
    assert r["actualizados"] == 0  # el auto que estaba tapado aparece al despejarse: no es una entrada
    assert {e["numero"]: e["estado"] for e in client.get("/espacios", headers=admin).json()}["A-01"] == "ocupado"
    assert not [e for e in client.get("/eventos", headers=admin).json() if e["tipo"] in ("entrada", "salida")]
    # pasado el calentamiento, los cambios vuelven a ser eventos reales
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-01", "ocupado": False}]})
    assert [e["tipo"] for e in client.get("/eventos", headers=admin).json() if "A-01" in e["descripcion"]] == ["salida"]

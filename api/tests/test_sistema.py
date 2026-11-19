from app import estado_vision
from helpers import ADMIN, DEMO, KEY, login

MODELO = {"camara": "CAM-01", "modelo": "YOLOv8n", "dispositivo": "cuda:0", "imgsz": 1280, "fps_video": 24, "fps_deteccion": 9.5,
          "latencia_ms": 105.3, "vehiculos": 79, "libres": 2, "ocupados": 6, "espacios": 8, "resolucion": "1280x720", "umbral_confianza": 0.35, "ids": ["A-01", "A-02"]}


def test_el_modelo_reporta_y_el_panel_lo_ve(client):
    estado_vision.limpiar()
    h = login(client, *ADMIN)
    antes = client.get("/sistema/estado", headers=h).json()
    assert antes["api"] == "ok" and antes["base_de_datos"]["estado"] == "ok" and antes["vision"] == [] and antes["vision_conectada"] is False

    assert client.post("/ingest/modelo", json=MODELO).status_code == 401  # exige la clave del servidor de visión
    assert client.post("/ingest/modelo", json=MODELO, headers=KEY).status_code == 200

    despues = client.get("/sistema/estado", headers=h).json()
    assert despues["vision_conectada"] is True
    v = despues["vision"][0]
    assert v["camara"] == "CAM-01" and v["modelo"] == "YOLOv8n" and v["vehiculos"] == 79 and v["hace_s"] < 5
    assert v["ids"] == ["A-01", "A-02"]  # el panel marca estos cajones como vigilados por el modelo
    assert despues["camaras"]["total"] == 3 and despues["espacios"]["total"] == 391 and despues["espacios"]["monitoreados"] == 0
    estado_vision.limpiar()


def test_estado_del_sistema_exige_sesion(client):
    assert client.get("/sistema/estado").status_code == 401


def test_datos_invalidos_del_modelo_se_rechazan(client):
    assert client.post("/ingest/modelo", json={**MODELO, "vehiculos": -3}, headers=KEY).status_code == 422


RUTAS_DE_ADMINISTRACION = ["/sistema/estado", "/sistema/estancias", "/sistema/vehiculos", "/sistema/historial?minutos=5", "/camaras", "/eventos", "/alertas", "/reportes/resumen"]


def test_quien_no_es_administrador_no_ve_el_estado_del_sistema_ni_las_camaras(client):
    estudiante, admin = login(client, *DEMO), login(client, *ADMIN)
    for ruta in RUTAS_DE_ADMINISTRACION:
        assert client.get(ruta, headers=estudiante).status_code == 403, ruta
    assert client.get("/sistema/estado", headers=admin).status_code == 200


def test_quien_no_es_administrador_ve_la_disponibilidad_pero_no_cuanto_lleva_cada_coche(client):
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-01", "ocupado": False}, {"numero": "A-02", "ocupado": False}]})
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-02", "ocupado": True}]})
    estudiante, admin = login(client, *DEMO), login(client, *ADMIN)
    a02 = next(e for e in client.get("/espacios", headers=estudiante).json() if e["numero"] == "A-02")
    assert a02["estado"] == "ocupado" and a02["monitoreado"] is True  # la disponibilidad sí
    assert a02["desde"] is None and a02["duracion_s"] is None and a02["desde_observado"] is False  # cuánto lleva estacionado, no
    assert client.get("/espacios/A-02", headers=estudiante).json()["duracion_s"] is None
    assert next(e for e in client.get("/espacios", headers=admin).json() if e["numero"] == "A-02")["duracion_s"] is not None  # el administrador sí lo ve


def test_la_ocupacion_por_hora_es_para_cualquier_usuario_con_sesion_y_solo_trae_promedios(client):
    assert client.get("/disponibilidad/por-hora").status_code == 401
    horas = client.get("/disponibilidad/por-hora", headers=login(client, *DEMO))
    assert horas.status_code == 200
    horas = horas.json()
    assert [h["hora"] for h in horas] == list(range(24))
    assert all(set(h) == {"hora", "ocupacion_media_pct", "muestras"} for h in horas)  # sin datos de personas ni de vehículos

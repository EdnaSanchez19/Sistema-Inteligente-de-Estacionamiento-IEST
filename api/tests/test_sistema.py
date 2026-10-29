from app import estado_vision
from helpers import DEMO, KEY, login

MODELO = {"camara": "CAM-01", "modelo": "YOLOv8n", "dispositivo": "cuda:0", "imgsz": 1280, "fps_video": 24, "fps_deteccion": 9.5,
          "latencia_ms": 105.3, "vehiculos": 79, "libres": 2, "ocupados": 6, "espacios": 8, "resolucion": "1280x720", "umbral_confianza": 0.35, "ids": ["A-01", "A-02"]}


def test_el_modelo_reporta_y_el_panel_lo_ve(client):
    estado_vision.limpiar()
    h = login(client, *DEMO)
    antes = client.get("/sistema/estado", headers=h).json()
    assert antes["api"] == "ok" and antes["base_de_datos"]["estado"] == "ok" and antes["vision"] == [] and antes["vision_conectada"] is False

    assert client.post("/ingest/modelo", json=MODELO).status_code == 401  # exige la clave del servidor de visión
    assert client.post("/ingest/modelo", json=MODELO, headers=KEY).status_code == 200

    despues = client.get("/sistema/estado", headers=h).json()
    assert despues["vision_conectada"] is True
    v = despues["vision"][0]
    assert v["camara"] == "CAM-01" and v["modelo"] == "YOLOv8n" and v["vehiculos"] == 79 and v["hace_s"] < 5
    assert v["ids"] == ["A-01", "A-02"]  # el panel marca estos cajones como vigilados por el modelo
    assert despues["camaras"]["total"] == 8 and despues["espacios"]["total"] == 391 and despues["espacios"]["monitoreados"] == 0
    estado_vision.limpiar()


def test_estado_del_sistema_exige_sesion(client):
    assert client.get("/sistema/estado").status_code == 401


def test_datos_invalidos_del_modelo_se_rechazan(client):
    assert client.post("/ingest/modelo", json={**MODELO, "vehiculos": -3}, headers=KEY).status_code == 422

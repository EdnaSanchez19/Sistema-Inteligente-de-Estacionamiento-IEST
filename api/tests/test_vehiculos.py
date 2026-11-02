"""Seguimiento de coches: el servidor de visión los reporta y el panel los consulta."""
import pytest

from app import seguimiento
from helpers import KEY, login


@pytest.fixture(autouse=True)
def _limpio():
    seguimiento.limpiar()
    yield
    seguimiento.limpiar()


def reporte(camara="CAM-02", **extra):
    return {"camara": camara, "vehiculos": [
        {"id": 1, "x": 0.3, "y": 0.4, "estado": "quieto", "quieto_s": 900.0, "visto_s": 1000.0, "cajon": None},
        {"id": 2, "x": 0.6, "y": 0.5, "estado": "en_movimiento", "quieto_s": 2.0, "visto_s": 30.0, "cajon": None},
        {"id": 3, "x": 0.7, "y": 0.5, "estado": "quieto", "quieto_s": 60.0, "visto_s": 400.0, "cajon": "A-12"},
    ], "resumen": {"total": 3, "quietos": 2, "en_movimiento": 1, "fuera_de_cajon": 1}, **extra}


def test_los_coches_reportados_aparecen_ordenados_por_tiempo_quieto(client):
    assert client.post("/ingest/vehiculos", headers=KEY, json=reporte()).json() == {"recibidos": 3}
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    d = client.get("/sistema/vehiculos", headers=h).json()
    assert (d["total"], d["quietos"], d["en_movimiento"], d["fuera_de_cajon"]) == (3, 2, 1, 1)
    assert [v["id"] for v in d["mas_tiempo_quietos"]] == [1, 3]  # el que lleva más quieto, primero; el que se mueve no aparece
    assert d["mas_tiempo_quietos"][0]["camara"] == "CAM-02" and d["mas_tiempo_quietos"][0]["nombre_camara"] == "Estacionamiento"
    assert d["camaras"][0]["camara"] == "CAM-02" and d["camaras"][0]["total"] == 3


def test_suma_las_camaras_y_olvida_la_que_dejo_de_reportar(client):
    client.post("/ingest/vehiculos", headers=KEY, json=reporte("CAM-01"))
    client.post("/ingest/vehiculos", headers=KEY, json=reporte("CAM-02"))
    h = login(client, "demo@iest.edu.mx", "demo-pass-123")
    assert client.get("/sistema/vehiculos", headers=h).json()["total"] == 6
    seguimiento._datos["CAM-01"]["_t"] -= seguimiento.CADUCA_S + 5  # CAM-01 dejó de reportar hace rato
    d = client.get("/sistema/vehiculos", headers=h).json()
    assert d["total"] == 3 and [c["camara"] for c in d["camaras"]] == ["CAM-02"]


def test_exige_la_clave_de_ingesta_y_una_camara_conocida_y_datos_validos(client):
    assert client.post("/ingest/vehiculos", json=reporte()).status_code == 401
    assert client.post("/ingest/vehiculos", headers=KEY, json=reporte("CAM-99")).status_code == 404
    malo = reporte()
    malo["vehiculos"][0]["estado"] = "volando"
    assert client.post("/ingest/vehiculos", headers=KEY, json=malo).status_code == 422
    assert client.get("/sistema/vehiculos").status_code == 401  # consultarlo exige sesión

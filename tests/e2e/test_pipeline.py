"""Cámara -> servidor de visión -> API -> base de datos -> lo que consulta la app.

Todo es real salvo la cámara (una imagen fija) y, en las pruebas "simuladas", el modelo YOLO,
que se sustituye por un detector programable para controlar qué "ve" la cámara en cada paso.
"""
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from conftest import wait_until

from parking_vision.config import CameraConfig, Config, Space
from parking_vision.occupancy import Detection
from parking_vision.pendant import PendantInfo
from parking_vision.publisher import ApiPublisher
from parking_vision.run import CameraWorker

ROOT = Path(__file__).resolve().parents[2]


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


class FakeDetector:
    """Sustituye a YOLO: devuelve las detecciones que la prueba le indique."""

    def __init__(self):
        self.dets: list[Detection] = []
        self.una_vez: list[Detection] | None = None  # se devuelve en UNA sola llamada y luego desaparece
        self.llamadas = 0

    def detect(self, frame):
        self.llamadas += 1
        if self.una_vez is not None:
            dets, self.una_vez = self.una_vez, None
            return dets
        return list(self.dets)


class FakePendants:
    def __init__(self, info: PendantInfo | None):
        self.info = info

    def read(self, frame, vehicles):
        return {0: self.info} if (self.info and vehicles) else {}


@pytest.fixture()
def escena(tmp_path):
    """Imagen fija de 640x480 con 3 cajones de 200x300 px en fila."""
    path = tmp_path / "camara.png"
    cv2.imwrite(str(path), np.full((480, 640, 3), 110, np.uint8))
    spaces = [Space(f"A-{i + 1:02d}", rect(10 + i * 205, 100, 205 + i * 205, 400)) for i in range(3)]
    return str(path), spaces


def arrancar(api, cam_id, source, spaces, detector, pendants=None) -> CameraWorker:
    cam = CameraConfig(id=cam_id, source=source, spaces=spaces, interval_s=0.2, confirm_occupied=2, confirm_free=2, offline_after_s=2.0, calentamiento_s=0.0)  # sin calentamiento: aquí sí queremos eventos de inmediato
    worker = CameraWorker(cam, Config(cameras=[cam]), detector, threading.Lock(), pendants, ApiPublisher(api.base, "clave-ingesta-e2e"))
    worker.start()
    return worker


def detener(worker: CameraWorker) -> None:
    worker.stop()
    worker.join(timeout=5)


def test_entrada_y_salida_de_un_vehiculo_con_colgante(api, escena):
    source, spaces = escena
    admin, demo = api.admin, api.demo
    det = FakeDetector()
    pend = FakePendants(PendantInfo(tipo="estudiante", codigo="IEST-004512", conf=0.93))
    w = arrancar(api, "CAM-01", source, spaces, det, pend)
    try:
        wait_until(lambda: api.get("/camaras", admin)[0]["estado"] == "en_linea")
        wait_until(lambda: {"A-01", "A-02", "A-03"} <= api.monitoreados(demo))  # el estado inicial (todo libre) ya quedó fijado
        assert api.estados(demo)["A-02"] == "libre"

        # Entra un auto al cajón A-02 (el centro de la imagen)
        det.dets = [Detection(225, 160, 395, 390, 0.91)]
        wait_until(lambda: api.estados(demo)["A-02"] == "ocupado")
        assert api.estados(demo)["A-01"] == "libre" and api.estados(demo)["A-03"] == "libre"
        entrada = next(e for e in api.get("/eventos", admin) if e["tipo"] == "entrada" and "A-02" in e["descripcion"])
        assert "A-02" in entrada["descripcion"] and "IEST-004512" in entrada["descripcion"]

        # El auto se va
        det.dets = []
        wait_until(lambda: api.estados(demo)["A-02"] == "libre")
        # el servidor de pruebas es compartido: se cuentan solo los eventos de este cajón
        tipos = [e["tipo"] for e in api.get("/eventos", admin) if "A-02" in e["descripcion"]]
        assert tipos.count("entrada") == 1 and tipos.count("salida") == 1
    finally:
        detener(w)


def test_parpadeos_cortos_no_generan_eventos(api, escena):
    """Una persona o un auto pasando por un instante (< confirmación) no cambia el estado."""
    source, spaces = escena
    admin, demo = api.admin, api.demo
    eventos_antes = len(api.get("/eventos", admin))
    det = FakeDetector()
    w = arrancar(api, "CAM-01", source, spaces, det)
    try:
        wait_until(lambda: api.get("/camaras", admin)[0]["estado"] == "en_linea")
        wait_until(lambda: det.llamadas >= 2)  # el estado inicial (todo libre) ya quedó fijado
        det.una_vez = [Detection(430, 160, 600, 390, 0.9)]  # visible en un único fotograma sobre A-03
        wait_until(lambda: det.una_vez is None)  # ya fue consumido por la cámara
        time.sleep(1.0)  # varios ciclos más sin el vehículo
        assert api.estados(demo)["A-03"] == "libre"
        assert len(api.get("/eventos", admin)) == eventos_antes
    finally:
        detener(w)


def test_camara_sin_senal_genera_alerta(api, escena):
    source, spaces = escena
    admin = api.admin
    # CAM-03 pasa a "en línea" y luego su fuente deja de dar video
    ApiPublisher(api.base, "clave-ingesta-e2e").camera_status("CAM-03", True)
    assert next(c for c in api.get("/camaras", admin) if c["camara"] == "CAM-03")["estado"] == "en_linea"
    w = arrancar(api, "CAM-03", str(Path(source).parent / "no_existe.mp4"), spaces, FakeDetector())
    try:
        wait_until(lambda: next(c for c in api.get("/camaras", admin) if c["camara"] == "CAM-03")["estado"] == "desconectada", timeout=15)
        assert any(e["tipo"] == "camara_desconectada" and "CAM-03" in e["descripcion"] for e in api.get("/eventos", admin))
    finally:
        detener(w)


def test_aviso_cuando_la_isla_se_llena(api, escena):
    """Isla C (40 cajones): al ocuparse los últimos, todos reciben el aviso en la app."""
    admin, demo = api.admin, api.demo
    numeros = [f"C-{i:02d}" for i in range(1, 41)]
    api.post("/ingest/ocupacion", api.key, {"camara": "CAM-02", "espacios": []})  # CAM-02 en línea
    # la cámara observa primero los 40 cajones (todos libres) y después se van ocupando: solo así hay cambios reales
    api.post("/ingest/ocupacion", api.key, {"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": False} for n in numeros]})
    api.post("/ingest/ocupacion", api.key, {"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": True} for n in numeros]})
    titulos = [n["titulo"] for n in api.get("/notificaciones", demo)]
    assert "Isla C llena" in titulos
    api.post("/ingest/ocupacion", api.key, {"camara": "CAM-03", "espacios": [{"numero": n, "ocupado": False} for n in numeros]})
    assert set(api.estados(admin)[n] for n in numeros) == {"libre"}


YOLO_MODEL = ROOT / "vision" / "models" / "yolov8n.pt"
FOTO_BUS = ROOT / "datasets" / "ejemplos" / "bus.jpg"


@pytest.mark.skipif(not (YOLO_MODEL.exists() and FOTO_BUS.exists()), reason="requiere vision/models/yolov8n.pt y datasets/ejemplos/bus.jpg")
def test_modelo_yolo_real_sobre_una_foto(api):
    """Con el modelo real: el autobús de la foto ocupa un cajón y una zona vacía queda libre."""
    from parking_vision.detector import VehicleDetector

    spaces = [Space("B-01", rect(60, 320, 740, 740)), Space("B-02", rect(600, 0, 800, 150))]
    admin, demo = api.admin, api.demo
    w = arrancar(api, "CAM-02", str(FOTO_BUS), spaces, VehicleDetector(str(YOLO_MODEL)))
    try:
        wait_until(lambda: api.estados(demo)["B-01"] == "ocupado", timeout=30)
        assert api.estados(demo)["B-02"] == "libre"
        assert {"B-01", "B-02"} <= api.monitoreados(demo)  # ya los observa una cámara
        # el autobús estaba desde el primer fotograma: es el estado inicial del cajón, no una entrada
        assert not [e for e in api.get("/eventos", admin) if e["tipo"] == "entrada" and "B-01" in e["descripcion"]]
    finally:
        detener(w)


def test_un_objeto_que_se_queda_en_un_cajon_vacio_lo_deja_obstruido(api, escena):
    """Una persona parada en A-01 (clase COCO 0) deja el cajón obstruido, con su evento; al irse vuelve a libre."""
    source, spaces = escena
    admin, demo = api.admin, api.demo
    det = FakeDetector()
    w = arrancar(api, "CAM-01", source, spaces, det)
    try:
        wait_until(lambda: {"A-01", "A-02", "A-03"} <= api.monitoreados(demo))
        det.dets = [Detection(40, 220, 90, 390, 0.9, cls=0)]  # persona con los pies dentro de A-01
        wait_until(lambda: api.estados(demo)["A-01"] == "obstruido", timeout=15)
        assert api.estados(demo)["A-02"] == "libre"
        espacio = next(e for e in api.get("/espacios?zona=A", demo) if e["numero"] == "A-01")
        assert espacio["objeto"] == "persona" and espacio["desde_observado"] is True
        assert any(e["tipo"] == "obstruccion" and "A-01" in e["descripcion"] for e in api.get("/eventos", admin))
        assert not any(e["tipo"] == "entrada" and "A-01" in e["descripcion"] for e in api.get("/eventos", admin))  # no es un vehículo
        det.dets = []
        wait_until(lambda: api.estados(demo)["A-01"] == "libre", timeout=15)
        assert any(e["tipo"] == "obstruccion_retirada" and "A-01" in e["descripcion"] for e in api.get("/eventos", admin))
    finally:
        detener(w)


def test_alguien_que_solo_cruza_no_obstruye_un_cajon(api, escena):
    source, spaces = escena
    demo = api.demo
    det = FakeDetector()
    w = arrancar(api, "CAM-01", source, spaces, det)
    try:
        wait_until(lambda: {"A-01", "A-02", "A-03"} <= api.monitoreados(demo))
        det.una_vez = [Detection(240, 220, 290, 390, 0.9, cls=0)]  # un solo fotograma sobre A-02
        wait_until(lambda: det.una_vez is None)
        time.sleep(1.5)
        assert api.estados(demo)["A-02"] == "libre"
    finally:
        detener(w)

"""DetectorCombinado: lo que detecta cualquiera de los modelos, sin repetir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.detector import DetectorCombinado  # noqa: E402
from parking_vision.occupancy import Detection  # noqa: E402


class Falso:
    imgsz, model = 640, object()

    def __init__(self, dets):
        self.dets = dets

    def detect(self, frame, mosaicos=(1, 1), traslape=0.2, interes=None):
        return self.dets


def test_suma_lo_que_ve_cada_modelo_y_no_repite_el_mismo_coche():
    a = Falso([Detection(0, 0, 100, 60, 0.5), Detection(300, 0, 400, 60, 0.9)])  # el segundo solo lo ve a
    b = Falso([Detection(2, 1, 101, 61, 0.8), Detection(600, 0, 700, 60, 0.7)])  # el primero es el mismo de a; el tercero solo lo ve b
    dets = DetectorCombinado([a, b]).detect(None)
    assert sorted((round(d.x1), round(d.conf, 1)) for d in dets) == [(2, 0.8), (300, 0.9), (600, 0.7)]  # el repetido se queda con el más confiable

"""Cajones que se marcan por detalle (motos): asfalto liso = libre, algo encima = ocupado."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import CameraConfig, Space  # noqa: E402
from parking_vision.run import densidad_de_bordes, process_frame  # noqa: E402


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


class SinDeteccion:
    def detect(self, frame, mosaicos=None):
        return []


def escena():
    frame = np.full((200, 400, 3), 70, np.uint8)  # asfalto liso
    rng = np.random.default_rng(0)
    frame[40:160, 220:360] = rng.integers(0, 255, (120, 140, 3), dtype=np.uint8)  # algo con mucho detalle
    return frame


def test_densidad_asfalto_liso_vs_con_algo_encima():
    f = escena()
    assert densidad_de_bordes(f, rect(20, 40, 160, 160)) < 1
    assert densidad_de_bordes(f, rect(220, 40, 360, 160)) > 10


def test_solo_los_cajones_con_detalle_min_se_marcan_por_detalle():
    cam = CameraConfig(id="C", source="x", spaces=[Space("LISO", rect(20, 40, 160, 160), 4.5), Space("MOTO", rect(220, 40, 360, 160), 4.5), Space("SIN", rect(220, 40, 360, 160))])
    estados = {s.id: s.occupied for s in process_frame(cam, SinDeteccion(), escena())[0]}
    assert estados == {"LISO": False, "MOTO": True, "SIN": False}  # sin detalle_min el cajón depende solo del modelo

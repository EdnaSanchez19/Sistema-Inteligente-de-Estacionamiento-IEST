"""La configuración de las cámaras reales (camaras/camaras.json) debe ser válida y conservar lo que se dibujó."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision"))

from parking_vision.config import load_config  # noqa: E402

CONFIG = ROOT / "camaras" / "camaras.json"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="falta camaras/camaras.json")


@pytest.fixture(scope="module")
def camaras():
    return {c.id: c for c in load_config(CONFIG).cameras}


def test_define_las_tres_camaras_reales(camaras):
    assert sorted(camaras) == ["CAM-01", "CAM-02", "CAM-03"]
    assert not camaras["CAM-03"].spaces  # la entrada no vigila cajones


def test_los_cajones_son_poligonos_convexos_y_no_se_repiten_entre_camaras(camaras):
    ids = [s.id for c in camaras.values() for s in c.spaces]
    assert len(ids) == len(set(ids))
    for c in camaras.values():
        for s in c.spaces:
            assert cv2.isContourConvex(s.polygon.astype(np.float32).reshape(-1, 1, 2)), f"{s.id} no es convexo"


def test_conserva_motos_y_biblioteca(camaras):
    """La esquina de motos (8 cajones con detalle_min) en CAM-01 y los 18 cajones visibles de la biblioteca en CAM-02."""
    motos = [s for s in camaras["CAM-01"].spaces if s.id.startswith("MOT-")]
    assert sorted(s.id for s in motos) == [f"MOT-{i:02d}" for i in range(1, 9)] and all(s.detalle_min for s in motos)
    assert len([s for s in camaras["CAM-02"].spaces if s.id.startswith("BIB-")]) == 18
    assert len([s for s in camaras["CAM-01"].spaces if s.id.startswith("CAS-")]) == 9  # lateral de la caseta

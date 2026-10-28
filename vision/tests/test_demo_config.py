"""La configuración de la demostración (demo/cameras_demo.json) debe ser válida: cajones convexos y bien ubicados."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision"))
sys.path.insert(0, str(ROOT / "scripts"))

from parking_vision.config import load_config  # noqa: E402

CONFIG = ROOT / "demo" / "cameras_demo.json"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="falta demo/cameras_demo.json (corre scripts/preparar_demo.py)")


def test_la_demo_define_las_camaras_esperadas():
    cams = {c.id: c for c in load_config(CONFIG).cameras}
    assert len(cams["CAM-01"].spaces) == 12  # isla A: 9 con auto + 3 de asfalto vacío (video generado con IA)
    if "CAM-02" in cams:  # isla B: cámara de seguridad real
        n = len(cams["CAM-02"].spaces)  # los 40 de siempre más los que se completaron con los coches y cajones que faltaban
        assert n >= 40 and [s.id for s in cams["CAM-02"].spaces] == [f"B-{i:02d}" for i in range(1, n + 1)]
    if "CAM-03" in cams:  # isla C: otra vista de la cámara de seguridad
        n = len(cams["CAM-03"].spaces)
        assert n >= 40 and [s.id for s in cams["CAM-03"].spaces] == [f"C-{i:02d}" for i in range(1, n + 1)]
    if "CAM-04" in cams:  # isla D: estacionamiento techado (solo se ven 8 cajones)
        assert all(s.id.startswith("D-") for s in cams["CAM-04"].spaces) and 1 <= len(cams["CAM-04"].spaces) <= 40
    ids = [s.id for c in cams.values() for s in c.spaces]
    assert len(ids) == len(set(ids)), "un cajón no puede pertenecer a dos cámaras"


@pytest.mark.parametrize("camara", ["CAM-01", "CAM-02", "CAM-03", "CAM-04"])
def test_los_cajones_son_poligonos_convexos_dentro_de_la_imagen(camara):
    cams = {c.id: c for c in load_config(CONFIG).cameras}
    if camara not in cams:
        pytest.skip(f"{camara} no está en la configuración")
    for s in cams[camara].spaces:
        pts = s.polygon.astype(np.float32)
        assert cv2.isContourConvex(pts.reshape(-1, 1, 2).astype(np.int32)), f"{s.id} no es convexo (la intersección exige polígonos convexos)"
        assert cv2.contourArea(pts) > 20, f"{s.id} es demasiado pequeño"
        assert pts[:, 0].min() >= -5 and pts[:, 0].max() <= 1285 and pts[:, 1].min() >= -5 and pts[:, 1].max() <= 725, f"{s.id} sale de la imagen"


@pytest.mark.parametrize("camara", ["CAM-01", "CAM-02", "CAM-03", "CAM-04"])
def test_los_cajones_de_una_camara_no_se_encimen_demasiado(camara):
    from parking_vision.occupancy import _intersection_area

    cams = {c.id: c for c in load_config(CONFIG).cameras}
    if camara not in cams:
        pytest.skip(f"{camara} no está en la configuración")
    sp = cams[camara].spaces
    for i, a in enumerate(sp):
        area_a = cv2.contourArea(a.polygon)
        for b in sp[i + 1 :]:
            solape = _intersection_area(a.polygon, b.polygon)
            assert solape / min(area_a, cv2.contourArea(b.polygon)) < 0.5, f"{a.id} y {b.id} se encima más de la mitad"


def test_el_generador_de_cajones_lejanos_da_16_cuadrilateros():
    from cajones_cam02 import cajones_lejanos

    quads = cajones_lejanos()
    assert len(quads) == 16 and all(len(q) == 4 for q in quads)

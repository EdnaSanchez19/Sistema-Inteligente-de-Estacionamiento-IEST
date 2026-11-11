"""Recortes (teselas), zonas de interés, precisión del modelo y normalización de la luz: lo que baja la latencia y aguanta la mala luz."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision import detector as det_mod  # noqa: E402
from parking_vision.config import CameraConfig, Space  # noqa: E402
from parking_vision.detector import VehicleDetector, rectangulos_de_interes, teselas  # noqa: E402
from parking_vision.iluminacion import LAVADO, NORMAL, OSCURO, QUEMADO, diagnostico, medir, normalizar  # noqa: E402
from parking_vision.occupancy import Detection, _envolventes, _intersection_area, _solapes  # noqa: E402
from parking_vision.run import process_frame  # noqa: E402


class DetectorSinModelo(VehicleDetector):
    """El detector real sin cargar YOLO: anota qué recortes se le pidieron."""

    def __init__(self):
        self.pedidos = []

    def _predecir(self, imagenes, origenes):
        self.pedidos.append(list(origenes))
        return [[] for _ in imagenes]


def cajon(id_, x, y, lado=40):
    return Space(id_, np.array([[x, y], [x + lado, y], [x + lado, y + lado], [x, y + lado]], np.float32))


def test_las_teselas_cubren_toda_la_imagen_y_se_traslapan():
    w, h = 2688, 1512
    ts = teselas(w, h, 3, 2, 0.2)
    assert len(ts) == 6
    cubierto = np.zeros((h, w), bool)
    for x0, y0, tw, th in ts:
        assert 0 <= x0 and x0 + tw <= w and 0 <= y0 and y0 + th <= h
        cubierto[y0:y0 + th, x0:x0 + tw] = True
    assert cubierto.all()
    assert ts[0][2] > w / 3 and ts[1][0] < ts[0][0] + ts[0][2]  # cada recorte es más ancho que un tercio: se traslapa con el vecino
    assert teselas(100, 50, 1, 1) == [(0, 0, 100, 50)]


def test_con_interes_solo_se_detecta_en_los_recortes_que_tocan_un_cajon():
    frame = np.zeros((600, 900, 3), np.uint8)
    d = DetectorSinModelo()
    d.detect(frame, (3, 2))
    assert len(d.pedidos[-1]) == 7  # imagen completa + 6 recortes
    d.detect(frame, (3, 2), interes=rectangulos_de_interes([cajon("A-01", 10, 10)]))  # un cajón en la esquina superior izquierda
    assert d.pedidos[-1] == [(0, 0), (0, 0)]  # imagen completa + el único recorte que lo toca
    d.detect(frame, (3, 2), interes=[])  # sin cajones: solo la imagen completa
    assert d.pedidos[-1] == [(0, 0)]
    d.detect(frame, (1, 1), interes=[])
    assert d.pedidos[-1] == [(0, 0)]


def test_process_frame_pasa_las_zonas_de_interes_solo_si_la_camara_lo_pide():
    frame = np.full((600, 900, 3), 110, np.uint8)
    for solo_cajones, recortes in ((False, 7), (True, 2)):
        d = DetectorSinModelo()
        cam = CameraConfig("CAM-X", "x", [cajon("A-01", 10, 10)], mosaicos=(3, 2), mosaicos_solo_cajones=solo_cajones)
        states, _, _ = process_frame(cam, d, frame)
        assert len(d.pedidos[-1]) == recortes and states[0].estado == "libre"


def test_el_atajo_de_los_solapes_da_lo_mismo_que_calcular_todas_las_intersecciones():
    rng = np.random.default_rng(1)
    spaces = []
    for i in range(60):  # cuadriláteros convexos (paralelogramos) repartidos por la imagen
        x, y, a, b, sesgo = rng.uniform(0, 900), rng.uniform(0, 500), rng.uniform(20, 90), rng.uniform(20, 90), rng.uniform(-30, 30)
        spaces.append(Space(f"C-{i}", np.array([[x, y], [x + a, y], [x + a + sesgo, y + b], [x + sesgo, y + b]], np.float32)))
    env = _envolventes(spaces)
    for _ in range(200):
        x, y = rng.uniform(-50, 950), rng.uniform(-50, 550)
        foot = Detection(x, y, x + rng.uniform(5, 200), y + rng.uniform(5, 200), 0.9).footprint(0.6)
        todas = np.array([_intersection_area(s.polygon, foot) for s in spaces])
        assert np.allclose(_solapes(spaces, env, foot), todas)


def test_media_precision_usa_el_argumento_que_entiende_la_version_instalada(monkeypatch):
    assert det_mod._args_precision(False) == {}
    args = det_mod._args_precision(True)
    assert args in ({"quantize": 16}, {"half": True})
    assert det_mod._hay_gpu("cpu") is False


def test_la_luz_normal_no_se_toca_y_la_mala_se_corrige():
    rng = np.random.default_rng(0)
    dia = np.clip(rng.normal(110, 40, (360, 640, 3)), 0, 255).astype(np.uint8)
    igual, estado = normalizar(dia)
    assert estado == NORMAL and igual is dia  # ni siquiera se copia

    noche = (dia * 0.22).astype(np.uint8)
    quemado = np.clip(dia.astype(np.float32) * 1.4 + 70, 0, 255).astype(np.uint8)
    niebla = (dia * 0.3 + 205 * 0.7).astype(np.uint8)
    assert (diagnostico(noche), diagnostico(quemado), diagnostico(niebla)) == (OSCURO, QUEMADO, LAVADO)

    aclarado, _ = normalizar(noche)
    assert 85 <= medir(aclarado)[0] <= 135 and aclarado.shape == noche.shape and aclarado.dtype == np.uint8
    oscurecido, _ = normalizar(quemado)
    assert medir(oscurecido)[0] < medir(quemado)[0] - 30
    con_contraste, _ = normalizar(niebla)
    assert medir(con_contraste)[1] > medir(niebla)[1] * 2

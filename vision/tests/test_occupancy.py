import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import Space, expand_env, load_config, save_spaces  # noqa: E402
from parking_vision.occupancy import Detection, OccupancyTracker, compute_occupancy  # noqa: E402
from parking_vision.pendant import assign_to_vehicles, parse_code  # noqa: E402


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


# Tres cajones de 100x200 px en fila
SPACES = [Space("A-01", rect(0, 0, 100, 200)), Space("A-02", rect(100, 0, 200, 200)), Space("A-03", rect(200, 0, 300, 200))]


def test_vehiculo_dentro_ocupa_solo_su_cajon():
    states = compute_occupancy(SPACES, [Detection(110, 20, 190, 190, 0.9)], footprint=1.0)
    assert [s.occupied for s in states] == [False, True, False]
    assert states[1].confidence == 0.9


def test_vehiculo_entre_dos_cajones_ocupa_solo_el_de_mayor_solape():
    # 70 px en A-02 y 30 en A-03 => solo A-02
    states = compute_occupancy(SPACES, [Detection(130, 20, 230, 190, 0.8)], footprint=1.0)
    assert [s.occupied for s in states] == [False, True, False]


def test_vehiculo_apenas_tocando_no_cuenta():
    states = compute_occupancy(SPACES, [Detection(190, 20, 260, 190, 0.8)], occupied_ratio=0.3, footprint=1.0)
    # A-02 solo recibe 10 px de 70 (14% de huella, <30% del cajón); A-03 recibe 60 px (>30%)
    assert [s.occupied for s in states] == [False, False, True]


def test_sin_detecciones_todo_libre():
    assert not any(s.occupied for s in compute_occupancy(SPACES, []))


def test_footprint_reduce_el_derrame_hacia_cajones_de_atras():
    # Recuadro alto que se desborda sobre un cajón "de atrás" (y 0-200) pero cuyo suelo está en y 200-400
    spaces = [Space("atras", rect(0, 0, 100, 200)), Space("frente", rect(0, 200, 100, 400))]
    det = Detection(0, 50, 100, 390, 0.9)
    states = compute_occupancy(spaces, [det], footprint=0.5)
    assert [s.occupied for s in states] == [False, True]


def test_tracker_antirrebote():
    t = OccupancyTracker(confirm_occupied=2, confirm_free=3)
    assert t.update({"a": False})[0].previous is None  # primera observación
    assert t.update({"a": True}) == []  # 1ª vez ocupado: aún no
    assert t.update({"a": True})[0].occupied is True  # 2ª: confirma
    assert t.update({"a": False}) == [] and t.update({"a": False}) == []
    assert t.update({"a": True}) == []  # parpadeo: reinicia la cuenta de "libre"
    assert t.update({"a": False}) == [] and t.update({"a": False}) == []
    assert t.update({"a": False})[0].occupied is False


def test_parse_code_y_asignacion_de_colgante():
    assert parse_code(["x", "iest 004512"], r"[A-Z]{2,6}-?\d{3,8}") == "IEST004512"
    assert parse_code(["???"], r"[A-Z]{2,6}-?\d{3,8}") is None
    vehicles = [Detection(0, 0, 100, 100, 0.9), Detection(200, 0, 300, 100, 0.9)]
    pendants = [Detection(220, 20, 240, 40, 0.8)]
    assert assign_to_vehicles(pendants, vehicles) == {1: 0}


def test_config_cajones_y_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("PASS", "secreta")
    assert expand_env("rtsp://u:${PASS}@h") == "rtsp://u:secreta@h"
    p = tmp_path / "cams.json"
    save_spaces(p, "CAM-01", "rtsp://u:${PASS}@h/1", SPACES)
    cfg = load_config(p)
    assert cfg.cameras[0].source == "rtsp://u:secreta@h/1"
    assert [s.id for s in cfg.cameras[0].spaces] == ["A-01", "A-02", "A-03"]
    assert "secreta" not in p.read_text()  # la credencial no se escribe en el archivo


def test_histeresis_un_auto_tapado_no_hace_parpadear_el_cajon():
    """Para marcar ocupado se exige conf; para soltar un cajón ya ocupado basta una detección más débil (conf_baja)."""
    from parking_vision.config import CameraConfig
    from parking_vision.run import process_frame

    class Detector:
        def __init__(self, dets):
            self.dets = dets

        def detect(self, frame):
            return self.dets

    cam = CameraConfig(id="C", source="x", spaces=SPACES[:1], conf=0.35, occupied_ratio=0.3, footprint=1.0)
    debil = [Detection(10, 20, 90, 190, 0.25)]  # entre 0.6 x conf (0.21) y conf (0.35)
    fuerte = [Detection(10, 20, 90, 190, 0.80)]
    assert process_frame(cam, Detector(debil), None, None)[0][0].occupied is False  # sin historia, una detección débil no basta
    assert process_frame(cam, Detector(debil), None, {"A-01": False})[0][0].occupied is False
    assert process_frame(cam, Detector(debil), None, {"A-01": True})[0][0].occupied is True  # ya estaba ocupado: se conserva
    assert process_frame(cam, Detector(fuerte), None, {"A-01": False})[0][0].occupied is True
    assert process_frame(cam, Detector([Detection(10, 20, 90, 190, 0.05)]), None, {"A-01": True})[0][0].occupied is False  # ruido muy débil: sí se libera

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import Space  # noqa: E402
from parking_vision.tools import condiciones  # noqa: E402
from parking_vision.tools.etiquetar import escribir_filas, espacio_en  # noqa: E402
from parking_vision.tools.procesar_video import cargar_etiquetas, etiqueta_en, metricas  # noqa: E402


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


SPACES = [Space("A-01", rect(0, 0, 100, 100)), Space("A-02", rect(100, 0, 200, 100))]


def test_metricas():
    m = metricas(tp=8, fp=2, tn=9, fn=1)
    assert m["n"] == 20
    assert round(m["exactitud"], 2) == 0.85 and round(m["precision"], 2) == 0.8 and round(m["recall"], 2) == 0.89
    assert metricas(0, 0, 0, 0)["exactitud"] == 0.0  # sin datos no divide por cero


def test_etiquetas_ida_y_vuelta_y_busqueda_por_tiempo(tmp_path):
    csv_path = tmp_path / "e.csv"
    escribir_filas(csv_path, 10.0, SPACES, [True, False])
    escribir_filas(csv_path, 40.0, SPACES, [False, False])  # agrega filas, no sobrescribe
    et = cargar_etiquetas(csv_path)
    assert et["A-01"] == [(10.0, True), (40.0, False)] and et["A-02"] == [(10.0, False), (40.0, False)]
    assert etiqueta_en(11.0, et["A-01"], tolerancia=2.0) is True
    assert etiqueta_en(25.0, et["A-01"], tolerancia=2.0) is None  # lejos de cualquier etiqueta


def test_clic_identifica_el_cajon():
    assert espacio_en(50, 50, SPACES) == 0
    assert espacio_en(150, 50, SPACES) == 1
    assert espacio_en(500, 500, SPACES) is None


def test_condiciones_cambian_la_imagen_sin_romper_el_formato():
    rng = np.random.default_rng(0)
    frame = np.full((120, 160, 3), 140, np.uint8)
    for nombre, fn in condiciones.CONDICIONES.items():
        out = fn(frame, rng)
        assert out.shape == frame.shape and out.dtype == np.uint8, nombre
        assert not np.array_equal(out, frame), nombre
    assert condiciones.noche(frame, rng).mean() < frame.mean() * 0.5  # la noche es mucho más oscura
    assert condiciones.sol_de_frente(frame, rng).mean() > frame.mean()  # el sol sobreexpone

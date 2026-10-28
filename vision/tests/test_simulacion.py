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
    assert et["A-01"] == [(10.0, "ocupado"), (40.0, "libre")] and et["A-02"] == [(10.0, "libre"), (40.0, "libre")]
    assert etiqueta_en(11.0, et["A-01"], tolerancia=2.0) == "ocupado"
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


def test_comparar_condiciones_empareja_por_iou_sin_reutilizar_detecciones():
    from parking_vision.occupancy import Detection
    from parking_vision.tools.comparar_condiciones import emparejar, iou

    base = [Detection(0, 0, 100, 100, 0.9), Detection(200, 0, 300, 100, 0.9)]
    assert iou(base[0], base[0]) == 1.0 and iou(base[0], base[1]) == 0.0
    # una detección desplazada 10 px sigue emparejando; la que no existe en la base cuenta como "extra"
    otras = [Detection(10, 0, 110, 100, 0.8), Detection(500, 0, 600, 100, 0.8)]
    assert emparejar(base, otras) == (1, 1)
    # una sola detección no puede emparejar con dos vehículos de la base
    assert emparejar([base[0], base[0]], [base[0]]) == (1, 0)


def test_estabilizador_sigue_un_desplazamiento_de_camara():
    import cv2

    from parking_vision.estabilizar import Estabilizador, proyectar

    rng = np.random.default_rng(1)
    escena = np.full((480, 640, 3), 120, np.uint8)
    for _ in range(250):  # textura con detalle para que haya puntos que seguir
        x, y, r = int(rng.integers(0, 640)), int(rng.integers(0, 480)), int(rng.integers(3, 14))
        cv2.circle(escena, (x, y), r, tuple(int(c) for c in rng.integers(0, 255, 3)), -1)
    est = Estabilizador()
    est.update(escena)
    mov = cv2.warpAffine(escena, np.float32([[1, 0, 30], [0, 1, 12]]), (640, 480), borderMode=cv2.BORDER_REPLICATE)
    H = est.update(mov)
    assert abs(H[0, 2] - 30) < 2 and abs(H[1, 2] - 12) < 2
    caja = proyectar([Space("A-01", rect(100, 100, 200, 200))], H)[0].polygon
    assert abs(caja[0][0] - 130) < 2 and abs(caja[0][1] - 112) < 2  # el cajón acompaña a la cámara

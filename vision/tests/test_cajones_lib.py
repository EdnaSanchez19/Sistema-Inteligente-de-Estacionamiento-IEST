"""Herramientas para armar cajones a partir de un video (scripts/cajones_lib.py)."""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "vision"))

import cajones_lib as L  # noqa: E402


def pavimento_con_rayas(xs, y_arriba=100, y_abajo=130):
    """Imagen gris con rayas blancas verticales (separadores de cajones) en las posiciones x dadas."""
    im = np.full((200, 400, 3), 70, np.uint8)
    for x in xs:
        cv2.line(im, (x, y_abajo), (x + 6, y_arriba), (255, 255, 255), 3)
    return im


def test_las_rayas_blancas_se_detectan_con_sus_extremos():
    rayas = L.rayas_blancas(pavimento_con_rayas([50, 120, 190]), (0, 80, 400, 150))
    assert len(rayas) == 3
    for r in rayas:
        assert r["arriba"][1] < r["abajo"][1]  # "arriba" tiene la y menor
    for r, esperado in zip(sorted(rayas, key=lambda r: r["cx"]), (53, 123, 193)):
        assert abs(r["cx"] - esperado) <= 2


def test_un_cajon_por_cada_par_de_rayas_consecutivas():
    rayas = L.rayas_blancas(pavimento_con_rayas([50, 120, 190, 260]), (0, 80, 400, 150))
    cajones = L.cajones_entre_rayas(rayas)
    assert len(cajones) == 3 and all(len(c) == 4 and L.es_convexo(c) for c in cajones)
    ancho = cajones[0][3][0] - cajones[0][0][0]
    assert 60 <= ancho <= 80  # la separación entre rayas


def test_rayas_demasiado_separadas_no_forman_cajon():
    rayas = L.rayas_blancas(pavimento_con_rayas([20, 300]), (0, 80, 400, 150))
    assert L.cajones_entre_rayas(rayas) == []  # 280 px de hueco: no es un cajón


def test_las_filas_se_separan_por_altura():
    arriba = pavimento_con_rayas([50, 120, 190], 40, 60)
    abajo = pavimento_con_rayas([50, 120, 190], 140, 160)
    im = cv2.max(arriba, abajo)
    cajones = L.cajones_entre_rayas(L.rayas_blancas(im, (0, 20, 400, 180)))
    assert len(cajones) == 4  # 2 por fila; no se mezclan rayas de filas distintas


def test_poligono_de_auto_es_la_mitad_inferior_del_recuadro():
    p = L.poligono_de_auto((100, 100, 200, 200))
    ys = sorted({y for _, y in p})
    assert ys == [145, 200] and L.es_convexo(p)


def test_iou_de_cajas():
    assert L.iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert L.iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert abs(L.iou((0, 0, 10, 10), (5, 0, 15, 10)) - 1 / 3) < 1e-6

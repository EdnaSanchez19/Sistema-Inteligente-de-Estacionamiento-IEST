"""Asignar cada coche al cajón que contiene el punto donde toca el suelo (cajones de tamaños muy distintos por la perspectiva)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import Space  # noqa: E402
from parking_vision.occupancy import Detection, compute_occupancy  # noqa: E402


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


# un cajón lejano (chico, arriba) y uno cercano (grande, justo debajo)
LEJOS, CERCA = Space("LEJOS", rect(0, 100, 300, 160)), Space("CERCA", rect(0, 160, 500, 320))


def coche():
    # su recuadro pisa más el cajón grande, pero su centro en el suelo (a 60 % de la altura) cae en el chico
    return Detection(20, 90, 280, 200, 0.9, 2)


def test_por_solape_gana_el_cajon_grande_y_por_punto_el_que_contiene_el_suelo_del_coche():
    por_solape = {s.id: s.occupied for s in compute_occupancy([LEJOS, CERCA], [coche()], 0.1, 0.6)}
    por_punto = {s.id: s.occupied for s in compute_occupancy([LEJOS, CERCA], [coche()], 0.1, 0.6, por_punto=True)}
    assert por_solape == {"LEJOS": False, "CERCA": True}  # el comportamiento de siempre no cambia
    assert por_punto == {"LEJOS": True, "CERCA": False}


def test_si_ningun_cajon_contiene_el_punto_se_usa_el_solape():
    lejos_del_suelo = Detection(20, 400, 280, 520, 0.9, 2)  # fuera de todo cajón
    assert not any(s.occupied for s in compute_occupancy([LEJOS, CERCA], [lejos_del_suelo], 0.2, 0.6, por_punto=True))

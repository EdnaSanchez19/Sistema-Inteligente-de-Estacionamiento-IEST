"""Seguimiento de vehículos: cada coche conserva su número, se sabe cuánto lleva quieto y en qué cajón está."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import Space  # noqa: E402
from parking_vision.occupancy import Detection  # noqa: E402
from parking_vision.seguimiento import EN_MOVIMIENTO, QUIETO, SeguidorVehiculos  # noqa: E402


def coche(x, y, ancho=100, alto=60, conf=0.8):
    return Detection(x, y, x + ancho, y + alto, conf, 2)


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


def test_un_coche_quieto_conserva_su_numero_y_acumula_tiempo():
    s = SeguidorVehiculos()
    for t in range(0, 20, 2):
        visibles = s.actualizar([coche(100 + (t % 3), 100)], float(t))  # tiembla un poco, como el recuadro de YOLO
    assert [v.id for v in visibles] == [1]
    v = visibles[0]
    assert v.estado(18.0, s.quieto_minimo_s) == QUIETO and 17 <= v.quieto_s(18.0) <= 18


def test_un_coche_que_se_mueve_conserva_el_numero_pero_no_esta_quieto():
    s = SeguidorVehiculos()
    for t in range(10):
        visibles = s.actualizar([coche(100 + 25 * t, 100)], float(t))  # avanza 25 px por fotograma: sigue traslapado
    assert [v.id for v in visibles] == [1]
    assert visibles[0].estado(9.0, s.quieto_minimo_s) == EN_MOVIMIENTO and visibles[0].quieto_s(9.0) < 2


def test_si_se_detiene_empieza_a_contar_desde_ahi():
    s = SeguidorVehiculos()
    for t in range(5):
        s.actualizar([coche(100 + 30 * t, 100)], float(t))
    for t in range(5, 20):
        visibles = s.actualizar([coche(220, 100)], float(t))
    v = visibles[0]
    assert v.id == 1 and v.estado(19.0, s.quieto_minimo_s) == QUIETO and 13 <= v.quieto_s(19.0) <= 16


def test_dos_coches_tienen_numeros_distintos_y_uno_nuevo_no_hereda_el_de_uno_que_se_fue():
    s = SeguidorVehiculos(olvidar_s=5.0)
    for t in range(3):
        s.actualizar([coche(100, 100), coche(400, 100)], float(t))
    ids = {v.id for v in s.actualizar([coche(100, 100), coche(400, 100)], 3.0)}
    assert ids == {1, 2}
    for t in range(4, 12):  # el segundo se va
        visibles = s.actualizar([coche(100, 100)], float(t))
    assert [v.id for v in visibles] == [1]
    for t in range(12, 15):  # llega uno nuevo en el mismo lugar
        visibles = s.actualizar([coche(100, 100), coche(400, 100)], float(t))
    assert sorted(v.id for v in visibles) == [1, 3]


def test_un_falso_positivo_de_un_solo_fotograma_no_cuenta():
    s = SeguidorVehiculos()
    assert s.actualizar([coche(100, 100), coche(500, 300)], 0.0) == []  # primera vez que se ven: aún no confirmados
    visibles = s.actualizar([coche(100, 100)], 1.0)  # el segundo desapareció
    assert [v.id for v in visibles] == [1]


def test_cajon_donde_esta_estacionado_o_ninguno():
    s = SeguidorVehiculos()
    cajones = [Space("A-01", rect(80, 90, 220, 170)), Space("A-02", rect(300, 90, 440, 170))]
    for t in range(3):
        visibles = s.actualizar([coche(100, 100), coche(600, 100)], float(t), cajones)
    por_id = {v.id: v.cajon for v in visibles}
    assert por_id == {1: "A-01", 2: None}  # el segundo está estacionado fuera de todo cajón
    assert s.resumen(visibles, 2.0) == {"total": 2, "quietos": 0, "en_movimiento": 2, "fuera_de_cajon": 0}  # aún no pasa el tiempo para llamarlos quietos


def test_reiniciar_olvida_todo():
    s = SeguidorVehiculos()
    for t in range(3):
        s.actualizar([coche(100, 100)], float(t))
    s.reiniciar()
    assert s.actualizar([coche(100, 100)], 3.0) == []  # vuelve a ser un coche sin confirmar

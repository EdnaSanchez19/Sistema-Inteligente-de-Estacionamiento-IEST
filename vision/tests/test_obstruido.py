"""Tercer estado de un cajón: obstruido = hay un objeto que no es un vehículo dentro de un cajón vacío."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parking_vision.config import CameraConfig, Space  # noqa: E402
from parking_vision.occupancy import Detection, OccupancyTracker, SpaceState, compute_states, con_estado_confirmado  # noqa: E402
from parking_vision.run import process_frame  # noqa: E402

PERSONA, MALETA, AUTO = 0, 28, 2


def rect(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)


# Tres cajones de 100x200 px en fila
SPACES = [Space("A-01", rect(0, 0, 100, 200)), Space("A-02", rect(100, 0, 200, 200)), Space("A-03", rect(200, 0, 300, 200))]


def estados(vehiculos=(), obstaculos=()):
    return [s.estado for s in compute_states(SPACES, list(vehiculos), list(obstaculos), footprint=1.0)]


def test_un_objeto_en_un_cajon_vacio_lo_deja_obstruido():
    # persona de pie con los pies dentro de A-02
    assert estados(obstaculos=[Detection(130, 60, 170, 190, 0.8, PERSONA)]) == ["libre", "obstruido", "libre"]


def test_el_estado_dice_que_objeto_es():
    st = compute_states(SPACES, [], [Detection(120, 120, 180, 190, 0.7, MALETA)], footprint=1.0)[1]
    assert st.obstructed and not st.occupied and st.obstacle == "maleta" and st.obstacle_box == (120, 120, 180, 190)


def test_un_vehiculo_manda_sobre_el_objeto():
    # persona junto al auto, dentro del mismo cajón: el cajón está ocupado, no obstruido
    est = estados([Detection(105, 20, 195, 190, 0.9, AUTO)], [Detection(110, 100, 130, 190, 0.8, PERSONA)])
    assert est == ["libre", "ocupado", "libre"]


def test_un_objeto_que_apenas_roza_el_cajon_no_lo_obstruye():
    # la base del objeto: 10 px dentro de A-02 y 40 px en A-03 => se asigna a A-03 y A-02 queda libre
    est = estados(obstaculos=[Detection(190, 100, 240, 190, 0.8, PERSONA)])
    assert est == ["libre", "libre", "obstruido"]
    # y si apenas toca el borde (menos de la mitad de su base dentro del cajón), no cuenta en ninguno
    assert estados(obstaculos=[Detection(195, 100, 400, 190, 0.8, PERSONA)]) == ["libre", "libre", "libre"]


def test_cada_objeto_obstruye_un_solo_cajon():
    est = estados(obstaculos=[Detection(60, 100, 140, 190, 0.8, PERSONA)])  # 40 px en A-01 y 40 en A-02
    assert est.count("obstruido") == 1


def test_el_objeto_mas_confiable_es_el_que_se_reporta():
    st = compute_states(SPACES, [], [Detection(110, 100, 140, 190, 0.5, PERSONA), Detection(150, 120, 190, 190, 0.9, MALETA)], footprint=1.0)[1]
    assert st.obstacle == "maleta" and st.confidence == 0.9


def test_el_estado_antiguo_de_dos_valores_sigue_funcionando():
    assert not any(s.obstructed for s in compute_states(SPACES, [Detection(110, 20, 190, 190, 0.9, AUTO)], []))
    assert SpaceState("x", True).estado == "ocupado" and SpaceState("x", False).estado == "libre"


# --- antirrebote con tres estados ---------------------------------------------------------------------
def _alimentar(t, estado, veces):
    cambios = []
    for _ in range(veces):
        cambios += t.update({"a": estado})
    return cambios


def test_alguien_que_solo_cruza_no_obstruye_el_cajon():
    t = OccupancyTracker(confirm_occupied=2, confirm_free=3, confirm_obstructed=6)
    t.update({"a": "libre"})
    assert _alimentar(t, "obstruido", 5) == []  # 5 observaciones seguidas no bastan
    assert _alimentar(t, "libre", 1) == [] and t.estado["a"] == "libre"
    assert _alimentar(t, "obstruido", 5) == []  # la cuenta empezó de nuevo


def test_un_objeto_que_se_queda_obstruye_tras_la_confirmacion():
    t = OccupancyTracker(confirm_occupied=2, confirm_free=3, confirm_obstructed=6)
    t.update({"a": "libre"})
    cambios = _alimentar(t, "obstruido", 6)
    assert [(c.estado_previo, c.estado) for c in cambios] == [("libre", "obstruido")]
    assert cambios[0].occupied is False and cambios[0].previous is False


def test_obstruido_nunca_es_el_estado_inicial():
    t = OccupancyTracker(confirm_occupied=2, confirm_free=3, confirm_obstructed=6)
    primero = t.update({"a": "obstruido"})
    assert primero[0].estado == "libre" and primero[0].estado_previo is None  # alguien de paso en el primer fotograma
    assert _alimentar(t, "obstruido", 4) == []  # ese primer fotograma ya cuenta como la 1ª observación
    assert [(c.estado_previo, c.estado) for c in _alimentar(t, "obstruido", 1)] == [("libre", "obstruido")]
    t2 = OccupancyTracker(confirm_occupied=2, confirm_free=3, confirm_obstructed=6)
    t2.update({"a": "obstruido"})
    assert _alimentar(t2, "libre", 1) == [] and t2.estado["a"] == "libre"  # se fue: nunca llegó a obstruir


def test_de_obstruido_a_libre_u_ocupado():
    t = OccupancyTracker(confirm_occupied=2, confirm_free=3, confirm_obstructed=6)
    t.update({"a": "libre"})
    _alimentar(t, "obstruido", 6)
    assert [(c.estado_previo, c.estado) for c in _alimentar(t, "libre", 3)] == [("obstruido", "libre")]
    _alimentar(t, "obstruido", 6)
    cambio = _alimentar(t, "ocupado", 2)
    assert [(c.estado_previo, c.estado) for c in cambio] == [("obstruido", "ocupado")] and cambio[0].previous is False


def test_si_el_estado_candidato_cambia_la_cuenta_se_reinicia():
    t = OccupancyTracker(confirm_occupied=3, confirm_free=3, confirm_obstructed=3)
    t.update({"a": "libre"})
    t.update({"a": "obstruido"}); t.update({"a": "obstruido"})
    t.update({"a": "ocupado"})  # otro candidato: no suma al anterior
    assert t.update({"a": "obstruido"}) == [] and t.estado["a"] == "libre"


def test_el_tracker_expone_la_vista_booleana_de_siempre():
    t = OccupancyTracker()
    t.update({"a": "obstruido", "b": "ocupado", "c": False})
    assert t.state == {"a": False, "b": True, "c": False}


# --- process_frame -------------------------------------------------------------------------------------
class Detector:
    def __init__(self, dets):
        self.dets = dets

    def detect(self, frame):
        return self.dets


def cam(**kw):
    return CameraConfig(id="C", source="x", spaces=SPACES, conf=0.35, occupied_ratio=0.3, footprint=1.0, **kw)


def test_process_frame_marca_obstruido_y_no_cuenta_el_objeto_como_vehiculo():
    persona = Detection(130, 60, 170, 190, 0.8, PERSONA)
    states, vehicles, todas = process_frame(cam(), Detector([persona]), None)
    assert [s.estado for s in states] == ["libre", "obstruido", "libre"] and vehicles == [] and persona in todas


def test_un_objeto_poco_confiable_se_ignora():
    assert process_frame(cam(), Detector([Detection(130, 60, 170, 190, 0.30, PERSONA)]), None)[0][1].estado == "libre"  # conf_obstaculo = 0.40


def test_se_pueden_desactivar_los_obstaculos():
    states = process_frame(cam(detectar_obstaculos=False), Detector([Detection(130, 60, 170, 190, 0.9, PERSONA)]), None)[0]
    assert all(s.estado == "libre" for s in states)


def test_la_histeresis_no_convierte_un_objeto_en_vehiculo():
    persona = Detection(130, 60, 170, 190, 0.25, PERSONA)  # débil
    states = process_frame(cam(), Detector([persona]), None, {"A-02": True})[0]
    assert states[1].estado == "libre"  # estaba ocupado, pero lo único que hay es un objeto débil: no es un vehículo


def test_con_estado_confirmado_conserva_el_detalle_solo_si_esta_obstruido():
    obs = compute_states(SPACES, [], [Detection(130, 60, 170, 190, 0.8, PERSONA)], footprint=1.0)
    conf = con_estado_confirmado(obs, {"A-01": "libre", "A-02": "obstruido", "A-03": "libre"})
    assert conf[1].obstructed and conf[1].obstacle == "persona"
    conf = con_estado_confirmado(obs, {"A-01": "libre", "A-02": "libre", "A-03": "libre"})  # aún no se confirma
    assert not conf[1].obstructed and conf[1].obstacle is None


# --- evaluación con tres clases ------------------------------------------------------------------------
def test_matriz_de_confusion_y_metricas_por_estado():
    from parking_vision.tools.procesar_video import matriz_confusion, metricas_por_estado

    pares = [("libre", "libre")] * 8 + [("libre", "obstruido")] * 2 + [("ocupado", "ocupado")] * 5 + [("obstruido", "obstruido")] * 3 + [("obstruido", "libre")]
    m = matriz_confusion(pares)
    assert m["libre"] == {"libre": 8, "ocupado": 0, "obstruido": 2} and m["obstruido"]["libre"] == 1
    r = metricas_por_estado(m)
    assert r["n"] == 19 and round(r["exactitud"], 3) == round(16 / 19, 3)
    assert r["por_estado"]["obstruido"]["precision"] == 3 / 5 and r["por_estado"]["obstruido"]["recall"] == 3 / 4
    assert r["por_estado"]["ocupado"]["precision"] == 1.0 and r["por_estado"]["ocupado"]["f1"] == 1.0


def test_una_clase_sin_casos_no_se_reporta_como_cero_por_ciento():
    from parking_vision.tools.procesar_video import matriz_confusion, metricas_por_estado

    r = metricas_por_estado(matriz_confusion([("libre", "libre"), ("ocupado", "ocupado")]))
    assert r["por_estado"]["obstruido"]["precision"] is None and r["por_estado"]["obstruido"]["recall"] is None


def test_etiquetas_de_tres_estados_ida_y_vuelta(tmp_path):
    from parking_vision.tools.etiquetar import escribir_filas
    from parking_vision.tools.procesar_video import cargar_etiquetas

    ruta = tmp_path / "e.csv"
    escribir_filas(ruta, 5.0, SPACES, ["libre", "obstruido", True])
    et = cargar_etiquetas(ruta)
    assert et["A-01"] == [(5.0, "libre")] and et["A-02"] == [(5.0, "obstruido")] and et["A-03"] == [(5.0, "ocupado")]


def test_las_etiquetas_antiguas_con_solo_ocupado_se_siguen_leyendo(tmp_path):
    from parking_vision.tools.procesar_video import cargar_etiquetas

    ruta = tmp_path / "vieja.csv"
    ruta.write_text("t_seg,espacio,ocupado\n0,A-01,1\n0,A-02,0\n", encoding="utf-8")
    assert cargar_etiquetas(ruta) == {"A-01": [(0.0, "ocupado")], "A-02": [(0.0, "libre")]}


def test_un_estado_de_etiqueta_desconocido_se_rechaza(tmp_path):
    import pytest
    from parking_vision.tools.procesar_video import cargar_etiquetas

    ruta = tmp_path / "mala.csv"
    ruta.write_text("t_seg,espacio,estado\n0,A-01,reservado\n", encoding="utf-8")
    with pytest.raises(ValueError, match="desconocido"):
        cargar_etiquetas(ruta)

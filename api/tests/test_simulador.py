"""Pruebas del simulador de islas (scripts/simulate_cameras.py): ocupación media, estancias y colgantes."""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from simulate_cameras import PERFIL_POR_DEFECTO, SimuladorIslas  # noqa: E402

from app.seed import colgantes_de_muestra  # noqa: E402


def crear(seed=1, n_colgantes=150, prob_colgante=0.85):
    camaras = {f"CAM-0{i}": [f"{'ABC'[i - 1]}-{k:02d}" for k in range(1, 41)] for i in (1, 2, 3)}
    return SimuladorIslas(camaras, PERFIL_POR_DEFECTO, hora_s=30, tick_s=3, colgantes=colgantes_de_muestra(n_colgantes), rnd=random.Random(seed), prob_colgante=prob_colgante)


def ocupados(sim) -> int:
    return sum(v is not None for v in sim.fin.values())


def test_el_primer_envio_trae_todos_los_cajones_y_ronda_el_55_por_ciento():
    sim = crear()
    primero = sim.paso(0)
    assert sum(len(v) for v in primero.values()) == 120  # 3 islas x 40
    assert 0.45 <= ocupados(sim) / 120 <= 0.65


def test_la_ocupacion_se_mantiene_cerca_del_perfil_durante_mucho_tiempo():
    sim = crear(seed=3)
    sim.paso(0)
    muestras = []
    for k in range(1, 400):  # 20 minutos reales de simulación (tick de 3 s)
        sim.paso(k * 3)
        muestras.append(ocupados(sim) / 120)
    assert 0.45 <= statistics.mean(muestras[100:]) <= 0.65  # tras el arranque, ronda el 55 %


def test_las_estancias_siguen_la_forma_del_perfil():
    sim = crear(seed=5)
    duraciones = [sim._duracion_s() / sim.hora_s for _ in range(4000)]  # en horas simuladas
    assert 2.9 <= statistics.mean(duraciones) <= 3.5  # media del dataset (2.87 h) + la fracción sorteada
    assert max(duraciones) < 11.5 and min(duraciones) >= 0


def test_los_colgantes_no_se_repiten_y_se_liberan_al_salir():
    sim = crear(seed=7)
    for k in range(0, 300):
        cambios = sim.paso(k * 3)
        en_uso = [c[0] for c, _ in [(v, None) for v in sim.colgante_de.values()]]
        assert len(en_uso) == len(set(en_uso))  # un colgante no puede estar en dos cajones a la vez
        for items in cambios.values():
            for it in items:
                assert it["ocupado"] or "colgante_codigo" not in it  # las salidas no llevan colgante
    assert len(sim.libres) + len(sim.colgante_de) == 150  # ninguno se pierde


def test_sin_colgantes_de_muestra_igual_funciona():
    sim = crear(n_colgantes=0)
    for k in range(50):
        for items in sim.paso(k * 3).values():
            assert all("colgante_codigo" not in it for it in items)


def test_no_simula_cajones_que_no_se_le_dieron():
    sim = crear()
    vistos = {it["numero"] for k in range(30) for items in sim.paso(k * 3).values() for it in items}
    assert vistos <= {n for ns in sim.camaras.values() for n in ns}

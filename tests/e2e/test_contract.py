"""Contrato app <-> API: los tipos de mobile/src/types.ts deben coincidir con lo que responde la API."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TYPES_TS = (ROOT / "mobile" / "src" / "types.ts").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "api"))


def campos_ts(interface: str) -> tuple[set[str], set[str]]:
    """(campos obligatorios, todos los campos) de una interfaz de nivel superior de types.ts."""
    body = re.search(rf"export interface {interface} \{{\n(.*?)\n\}}", TYPES_TS, re.S).group(1)
    todos, obligatorios = set(), set()
    for m in re.finditer(r"^  (\w+)(\?)?:", body, re.M):
        todos.add(m.group(1))
        if not m.group(2):
            obligatorios.add(m.group(1))
    return obligatorios, todos


def valores_ts(tipo: str) -> set[str]:
    linea = re.search(rf"export type {tipo} =([^;]+);", TYPES_TS).group(1)
    return set(re.findall(r"'([^']+)'", linea))


@pytest.fixture(scope="module")
def respuestas(api):
    admin, demo = api.admin, api.demo
    api.post("/notificaciones", admin, {"titulo": "Prueba", "mensaje": "contrato"})
    api.post("/ingest/ocupacion", api.key, {"camara": "CAM-01", "espacios": [{"numero": "A-10", "ocupado": True, "colgante_codigo": "IEST-004512"}]})
    return {
        "Usuario": api.get("/auth/me", demo),
        "Espacio": api.get("/espacios", demo)[0],
        "Vehiculo": api.get("/vehiculos/mios", demo)[0],
        "Notificacion": api.get("/notificaciones", demo)[0],
        "Evento": api.get("/eventos", admin)[0],
        "AlertaCamara": api.get("/camaras", admin)[0],
    }


@pytest.mark.parametrize("interfaz", ["Usuario", "Espacio", "Vehiculo", "Notificacion", "Evento", "AlertaCamara"])
def test_la_api_entrega_los_campos_que_espera_la_app(respuestas, interfaz):
    obligatorios, _ = campos_ts(interfaz)
    faltan = obligatorios - respuestas[interfaz].keys()
    assert not faltan, f"La API no devuelve {sorted(faltan)} en {interfaz}"


def test_vehiculo_trae_el_colgante_anidado(respuestas):
    assert {"codigo", "tipo"} <= respuestas["Vehiculo"]["colgante"].keys()


@pytest.mark.parametrize(
    "tipo_ts, enum_api",
    [("EstadoEspacio", "EstadoEspacio"), ("TipoEspacio", "TipoEspacio"), ("TipoEvento", "TipoEvento"), ("Rol", "Rol")],
)
def test_los_valores_de_los_enums_coinciden(tipo_ts, enum_api):
    from app import models

    assert valores_ts(tipo_ts) == {m.value for m in getattr(models, enum_api)}

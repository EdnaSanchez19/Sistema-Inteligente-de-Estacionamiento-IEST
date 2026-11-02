"""Seguimiento de vehículos en memoria: los coches que sigue cada cámara (número, si están quietos y desde cuándo).

Como el estado del modelo (`estado_vision`), es información en vivo que se renueva cada pocos segundos y no se guarda en la
base de datos: si la API se reinicia, se vuelve a llenar en cuanto el servidor de visión reporta.
"""
import time
from threading import Lock

CADUCA_S = 30  # un reporte más viejo que esto ya no se muestra: la cámara dejó de reportar

_datos: dict[str, dict] = {}
_lock = Lock()


def registrar(camara: str, vehiculos: list[dict], resumen: dict) -> None:
    with _lock:
        _datos[camara] = {"vehiculos": vehiculos, "resumen": resumen, "_t": time.monotonic()}


def listar() -> list[dict]:
    """Un registro por cámara con reporte reciente."""
    ahora = time.monotonic()
    with _lock:
        copia = {k: dict(v) for k, v in _datos.items()}
    salida = []
    for camara, d in sorted(copia.items()):
        hace = ahora - d.pop("_t")
        if hace <= CADUCA_S:
            salida.append({**d, "camara": camara, "hace_s": round(hace, 1)})
    return salida


def limpiar() -> None:
    with _lock:
        _datos.clear()

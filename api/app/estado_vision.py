"""Estado del servidor de visión en memoria: lo que reporta el modelo (FPS, latencia, vehículos).

Es información de monitoreo que se renueva cada pocos segundos, no un dato que haya que conservar: por eso vive en
memoria y no en la base de datos. Si la API se reinicia, se vuelve a llenar en cuanto el servidor de visión reporta.
"""
import time
from threading import Lock

_datos: dict[str, dict] = {}
_lock = Lock()


def registrar(camara: str, datos: dict) -> None:
    with _lock:
        _datos[camara] = {**datos, "_t": time.monotonic()}


def listar() -> list[dict]:
    """Un registro por cámara, con los segundos transcurridos desde su último reporte."""
    ahora = time.monotonic()
    with _lock:
        copia = {k: dict(v) for k, v in _datos.items()}
    salida = []
    for camara, d in sorted(copia.items()):
        t = d.pop("_t")
        salida.append({**d, "camara": camara, "hace_s": round(ahora - t, 1)})
    return salida


def limpiar() -> None:
    with _lock:
        _datos.clear()

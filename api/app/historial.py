"""Serie de ocupación en memoria para la gráfica del panel (cuántos cajones monitoreados están libres u ocupados).

Se muestrea cada pocos segundos mientras la API está arriba. Es información para ver la tendencia reciente, no un
registro de auditoría (para eso están los eventos en la base de datos): si la API se reinicia, la serie empieza de nuevo.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock

MAX_PUNTOS = 2880  # 8 horas a una muestra cada 10 s
_serie: deque[dict] = deque(maxlen=MAX_PUNTOS)
_lock = Lock()


def registrar(libres: int, ocupados: int, monitoreados: int, ahora: datetime | None = None, obstruidos: int = 0) -> None:
    with _lock:
        _serie.append({"t": (ahora or datetime.now(timezone.utc)).isoformat(), "libres": libres, "ocupados": ocupados, "obstruidos": obstruidos, "monitoreados": monitoreados})


def ultimos(minutos: int) -> list[dict]:
    limite = (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()
    with _lock:
        return [p for p in _serie if p["t"] >= limite]


def limpiar() -> None:
    with _lock:
        _serie.clear()

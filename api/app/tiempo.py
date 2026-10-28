"""Cuánto lleva un cajón en su estado actual (para un coche: cuánto lleva estacionado sin moverse)."""
from datetime import datetime, timezone


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # SQLite devuelve fechas sin zona; se guardan en UTC


def segundos_desde(desde: datetime | None, ahora: datetime | None = None) -> int | None:
    if desde is None:
        return None
    return max(0, int(((ahora or datetime.now(timezone.utc)) - _utc(desde)).total_seconds()))


def formatear(segundos: float) -> str:
    """90 -> '1 min', 3700 -> '1 h 1 min', 40 -> '40 s'."""
    s = int(segundos)
    if s < 60:
        return f"{s} s"
    m = s // 60
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} h {m} min" if m else f"{h} h"
    d, h = divmod(h, 24)
    return f"{d} d {h} h" if h else f"{d} d"

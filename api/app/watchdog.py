"""Vigilancia de cámaras del lado del servidor.

El servidor de visión avisa cuando pierde la señal RTSP de una cámara, pero si el propio servidor
de visión se cae nadie avisaría. Aquí se marca como desconectada toda cámara que lleve demasiado
tiempo sin enviar datos.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from . import historial
from .models import Camara, Espacio, EstadoCamara, EstadoEspacio, Evento, TipoEvento

log = logging.getLogger("watchdog")


def revisar_camaras(db: Session, timeout_s: int, ahora: datetime | None = None) -> list[str]:
    """Marca como desconectadas las cámaras en línea sin señal reciente. Devuelve sus códigos."""
    ahora = ahora or datetime.now(timezone.utc)
    limite = ahora - timedelta(seconds=timeout_s)
    caidas = []
    for cam in db.scalars(select(Camara).where(Camara.estado == EstadoCamara.en_linea)):
        ultima = cam.ultima_senal
        if ultima is not None and ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        if ultima is None or ultima < limite:
            cam.estado = EstadoCamara.desconectada
            db.add(Evento(tipo=TipoEvento.camara_desconectada, descripcion=f"{cam.codigo} sin datos desde hace más de {timeout_s} s", camara_id=cam.id))
            caidas.append(cam.codigo)
    if caidas:
        db.commit()
    return caidas


def muestrear_ocupacion(db: Session) -> None:
    """Guarda un punto de la serie de ocupación con los cajones que una cámara ya observa."""
    estados = db.scalars(select(Espacio.estado).where(Espacio.monitoreado.is_(True))).all()
    historial.registrar(sum(e == EstadoEspacio.libre for e in estados), sum(e == EstadoEspacio.ocupado for e in estados), len(estados))


async def muestrear(session_factory, cada_s: int = 10) -> None:
    while True:
        await asyncio.sleep(cada_s)
        try:
            with session_factory() as db:
                muestrear_ocupacion(db)
        except Exception:
            log.exception("Falló el muestreo de ocupación")


async def vigilar(session_factory) -> None:
    s = get_settings()
    while True:
        await asyncio.sleep(s.camera_check_interval_s)
        try:
            with session_factory() as db:
                for codigo in revisar_camaras(db, s.camera_timeout_s):
                    log.warning("Cámara %s sin señal", codigo)
        except Exception:
            log.exception("Falló la revisión de cámaras")

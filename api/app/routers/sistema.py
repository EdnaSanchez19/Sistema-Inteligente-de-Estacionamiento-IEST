"""Estado general del sistema para el panel: API, base de datos, modelo de visión y cámaras."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import estado_vision, historial
from ..auth import get_current_user
from ..db import get_db
from ..models import Camara, Espacio, EstadoCamara, EstadoEspacio, Evento, Usuario, Zona
from ..schemas import _utc
from ..tiempo import segundos_desde

router = APIRouter(prefix="/sistema", tags=["sistema"])

VISION_ACTIVA_S = 15  # un reporte más viejo que esto se considera "sin conexión"


@router.get("/estado")
def estado(_: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        bd = "ok"
    except Exception:
        bd = "error"
    vision = estado_vision.listar()
    # Solo cuentan los cajones que una cámara ya observó: los demás no tienen un estado real que mostrar.
    cuenta = dict(db.execute(select(Espacio.estado, func.count()).where(Espacio.monitoreado.is_(True)).group_by(Espacio.estado)).all())
    total = db.scalar(select(func.count()).select_from(Espacio)) or 0
    monitoreados = sum(cuenta.values())
    desde = datetime.now(timezone.utc) - timedelta(seconds=60)
    return {
        "version": "1.0.0",
        "hora": datetime.now(timezone.utc).isoformat(),
        "api": "ok",
        "base_de_datos": {"estado": bd, "motor": db.get_bind().dialect.name},
        "vision": vision,
        "vision_conectada": any(v["hace_s"] <= VISION_ACTIVA_S for v in vision),
        "camaras": {
            "total": db.scalar(select(func.count()).select_from(Camara)) or 0,
            "en_linea": db.scalar(select(func.count()).select_from(Camara).where(Camara.estado == EstadoCamara.en_linea)) or 0,
        },
        "espacios": {**{e.value: int(cuenta.get(e, 0)) for e in EstadoEspacio}, "monitoreados": monitoreados, "total": total, "sin_monitoreo": total - monitoreados},
        "eventos_ultimo_minuto": db.scalar(select(func.count()).select_from(Evento).where(Evento.creado_en >= desde)) or 0,
    }


@router.get("/estancias")
def estancias(estado: EstadoEspacio = EstadoEspacio.ocupado, limite: int = Query(10, ge=1, le=100), _: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Los cajones que llevan más tiempo en un estado (por defecto, los coches que llevan más tiempo estacionados).

    Solo cajones que una cámara observa. `desde_observado` False significa que la duración es un mínimo: la cámara empezó
    a verlo así, no vio el momento en que cambió.
    """
    q = (select(Espacio, Zona.nombre).join(Zona).where(Espacio.monitoreado.is_(True), Espacio.estado == estado, Espacio.estado_desde.is_not(None))
         .order_by(Espacio.estado_desde).limit(limite))
    return [{"numero": e.numero, "zona": zona, "desde": _utc(e.estado_desde), "duracion_s": segundos_desde(e.estado_desde), "desde_observado": bool(e.inicio_observado), "objeto": e.objeto} for e, zona in db.execute(q).all()]


@router.get("/historial")
def serie_de_ocupacion(minutos: int = Query(60, ge=1, le=480), _: Usuario = Depends(get_current_user)) -> list[dict]:
    """Puntos {t, libres, ocupados, obstruidos, monitoreados} de los últimos minutos (en memoria; se reinicia con la API)."""
    return historial.ultimos(minutos)

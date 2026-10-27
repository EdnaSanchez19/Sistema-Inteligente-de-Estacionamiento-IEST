"""Consultas que usa la app móvil."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user, require_admin
from ..db import get_db
from ..models import Camara, Espacio, Evento, Notificacion, Usuario, Vehiculo, Zona
from ..models import Rol
from ..schemas import CamaraOut, ColganteOut, EspacioDetalleOut, EspacioOut, EventoCajonOut, EventoOut, NotificacionOut, VehiculoOut

router = APIRouter(tags=["consulta"])


@router.get("/espacios", response_model=list[EspacioOut])
def espacios(zona: str | None = None, _: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Espacio).join(Zona).options(selectinload(Espacio.zona)).order_by(Zona.nombre, Espacio.numero)
    if zona:
        q = q.where(Zona.nombre == zona)
    return [EspacioOut.of(e) for e in db.scalars(q)]


@router.get("/espacios/{numero}", response_model=EspacioDetalleOut)
def detalle_de_espacio(numero: str, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    esp = db.scalar(select(Espacio).where(Espacio.numero == numero).options(selectinload(Espacio.zona), selectinload(Espacio.camara)))
    if esp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"El cajón {numero} no existe")
    out = EspacioDetalleOut(**EspacioOut.of(esp).model_dump(), camara=esp.camara.codigo if esp.camara else None)
    if user.rol == Rol.admin:  # quién estaciona y el historial son datos de auditoría
        if esp.colgante_actual:
            out.colgante = ColganteOut(codigo=esp.colgante_actual.codigo, tipo=esp.colgante_actual.tipo.value)
        q = select(Evento).where(Evento.espacio_id == esp.id).order_by(Evento.creado_en.desc(), Evento.id.desc()).limit(15)
        out.historial = [EventoCajonOut(id=e.id, tipo=e.tipo.value, descripcion=e.descripcion, fecha=e.creado_en, confianza=e.confianza) for e in db.scalars(q)]
    return out


@router.get("/vehiculos/mios", response_model=list[VehiculoOut])
def mis_vehiculos(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Vehiculo).where(Vehiculo.usuario_id == user.id).options(selectinload(Vehiculo.colgante))
    return [VehiculoOut.of(v) for v in db.scalars(q)]


@router.get("/notificaciones", response_model=list[NotificacionOut])
def notificaciones(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Notificacion).where(or_(Notificacion.usuario_id == user.id, Notificacion.usuario_id.is_(None))).order_by(Notificacion.creado_en.desc()).limit(50)
    return [NotificacionOut.of(n) for n in db.scalars(q)]


@router.get("/eventos", response_model=list[EventoOut])
def eventos(limit: int = Query(50, ge=1, le=200), _: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    return [EventoOut.of(e) for e in db.scalars(select(Evento).order_by(Evento.creado_en.desc(), Evento.id.desc()).limit(limit))]


@router.get("/camaras", response_model=list[CamaraOut])
def camaras(_: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    return [CamaraOut.of(c) for c in db.scalars(select(Camara).options(selectinload(Camara.zona)).order_by(Camara.codigo))]

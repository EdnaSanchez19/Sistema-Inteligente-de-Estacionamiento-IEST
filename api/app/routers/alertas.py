"""Alertas para el operador (solo administradores): verlas, marcarlas como atendidas y forzar una revisión."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import alertas
from ..auth import require_admin
from ..db import get_db
from ..models import Alerta, Espacio, Usuario, utcnow
from ..schemas import AlertaOut

router = APIRouter(prefix="/alertas", tags=["alertas"], dependencies=[Depends(require_admin)])


def _consulta():
    return select(Alerta).options(selectinload(Alerta.espacio).selectinload(Espacio.zona), selectinload(Alerta.camara), selectinload(Alerta.atendida_por))


@router.get("", response_model=list[AlertaOut])
def listar(estado: Literal["activas", "todas"] = "activas", limite: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """Las alertas activas (por defecto) o también las ya resueltas, de la más reciente a la más antigua."""
    q = _consulta().order_by(Alerta.activa.desc(), Alerta.creada_en.desc(), Alerta.id.desc()).limit(limite)
    if estado == "activas":
        q = q.where(Alerta.activa.is_(True))
    return [AlertaOut.of(a) for a in db.scalars(q)]


@router.post("/{alerta_id}/atender", response_model=AlertaOut)
def atender(alerta_id: int, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """Marca la alerta como atendida (alguien ya la vio). Sigue activa hasta que la condición termine."""
    alerta = db.scalar(_consulta().where(Alerta.id == alerta_id))
    if alerta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Alerta {alerta_id} no existe")
    if alerta.atendida_en is None:
        alerta.atendida_en, alerta.atendida_por_id = utcnow(), admin.id
        db.commit()
        db.refresh(alerta)
    return AlertaOut.of(alerta)


@router.post("/evaluar")
def evaluar(db: Session = Depends(get_db)) -> dict:
    """Revisa las reglas ahora mismo en lugar de esperar al siguiente ciclo del vigilante."""
    creadas, cerradas = alertas.evaluar(db)
    return {"creadas": creadas, "cerradas": cerradas}

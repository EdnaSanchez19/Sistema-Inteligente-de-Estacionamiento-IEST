"""Endpoints que usa el servidor de visión para publicar resultados (autenticados con X-API-Key)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_ingest_key
from ..db import get_db
from ..models import Camara, Colgante, Espacio, EstadoCamara, EstadoEspacio, Evento, Notificacion, TipoEvento, Zona, utcnow
from ..schemas import CamaraEstadoIn, OcupacionIn

UMBRAL_CASI_LLENA = 3  # libres a partir de los cuales se avisa a todos los usuarios

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_ingest_key)])


def _camara(db: Session, codigo: str) -> Camara:
    cam = db.scalar(select(Camara).where(Camara.codigo == codigo))
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Cámara {codigo} no registrada")
    return cam


def _libres(db: Session, zona_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Espacio).where(Espacio.zona_id == zona_id, Espacio.estado == EstadoEspacio.libre)) or 0


def _avisar_cambio_de_zona(db: Session, zona_id: int, antes: int, despues: int) -> None:
    """Notifica a todos cuando una zona se llena o queda casi llena (solo al cruzar el umbral)."""
    zona = db.get(Zona, zona_id)
    if despues == 0 and antes > 0:
        db.add(Notificacion(titulo=f"Zona {zona.nombre} llena", mensaje=f"Ya no hay espacios libres en la zona {zona.nombre}."))
    elif 0 < despues <= UMBRAL_CASI_LLENA < antes:
        db.add(Notificacion(titulo=f"Zona {zona.nombre} casi llena", mensaje=f"Quedan {despues} espacios libres en la zona {zona.nombre}."))


def _marcar_en_linea(db: Session, cam: Camara) -> None:
    if cam.estado != EstadoCamara.en_linea:
        db.add(Evento(tipo=TipoEvento.camara_restablecida, descripcion=f"Cámara {cam.codigo} restablecida", camara_id=cam.id))
    cam.estado = EstadoCamara.en_linea
    cam.ultima_senal = utcnow()


@router.post("/ocupacion")
def ocupacion(data: OcupacionIn, db: Session = Depends(get_db)) -> dict:
    cam = _camara(db, data.camara)
    _marcar_en_linea(db, cam)
    if data.baja_confianza:
        db.add(Evento(tipo=TipoEvento.error_deteccion, descripcion=f"Confianza baja en {cam.codigo}", camara_id=cam.id))

    espacios = {e.numero: e for e in db.scalars(select(Espacio).where(Espacio.camara_id == cam.id))}
    libres_antes = _libres(db, cam.zona_id)
    desconocidos, cambios = [], 0
    for item in data.espacios:
        esp = espacios.get(item.numero)
        if esp is None:
            desconocidos.append(item.numero)
            continue
        # Reservados y fuera de servicio los decide un administrador, no la cámara.
        if esp.estado not in (EstadoEspacio.libre, EstadoEspacio.ocupado):
            continue
        nuevo = EstadoEspacio.ocupado if item.ocupado else EstadoEspacio.libre
        if nuevo == esp.estado:
            continue
        cambios += 1
        colgante_previo = esp.colgante_actual
        if item.ocupado:
            colgante = db.scalar(select(Colgante).where(Colgante.codigo == item.colgante_codigo, Colgante.activo.is_(True))) if item.colgante_codigo else None
            if colgante:
                desc = f"Entrada en {esp.numero}: colgante {colgante.codigo}"
            elif item.colgante_codigo:
                desc = f"Entrada en {esp.numero}: colgante {item.colgante_codigo} no registrado"
            else:
                desc = f"Entrada en {esp.numero}: vehículo sin colgante identificado"
            esp.colgante_actual = colgante
            db.add(Evento(tipo=TipoEvento.entrada, descripcion=desc, espacio_id=esp.id, camara_id=cam.id, colgante_id=colgante.id if colgante else None, confianza=item.confianza))
        else:
            desc = f"Salida de {esp.numero}" + (f": colgante {colgante_previo.codigo}" if colgante_previo else "")
            esp.colgante_actual = None
            db.add(Evento(tipo=TipoEvento.salida, descripcion=desc, espacio_id=esp.id, camara_id=cam.id, colgante_id=colgante_previo.id if colgante_previo else None))
        esp.estado = nuevo
    if cambios:
        db.flush()
        _avisar_cambio_de_zona(db, cam.zona_id, libres_antes, _libres(db, cam.zona_id))
    db.commit()
    return {"actualizados": cambios, "desconocidos": desconocidos}


@router.post("/camara-estado")
def camara_estado(data: CamaraEstadoIn, db: Session = Depends(get_db)) -> dict:
    cam = _camara(db, data.camara)
    if data.en_linea:
        _marcar_en_linea(db, cam)
    else:
        if cam.estado != EstadoCamara.desconectada:
            db.add(Evento(tipo=TipoEvento.camara_desconectada, descripcion=f"Se perdió la señal RTSP de {cam.codigo}", camara_id=cam.id))
        cam.estado = EstadoCamara.desconectada
    db.commit()
    return {"estado": cam.estado.value}

"""Administración (solo rol admin): usuarios, vehículos, colgantes, espacios y avisos."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import require_admin
from ..db import get_db
from ..models import Colgante, Espacio, EstadoEspacio, Evento, Notificacion, TipoEvento, Usuario, Vehiculo
from ..schemas import (
    ColganteAdminOut,
    ColganteIn,
    ColgantePatch,
    EspacioOut,
    EspacioPatch,
    NotificacionIn,
    NotificacionOut,
    UsuarioIn,
    UsuarioOut,
    UsuarioPatch,
    VehiculoIn,
    VehiculoOut,
)
from ..security import hash_password

router = APIRouter(tags=["administración"], dependencies=[Depends(require_admin)])


def _get_or_404(db: Session, model, ident: int, nombre: str):
    obj = db.get(model, ident)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nombre} {ident} no existe")
    return obj


def _commit(db: Session, conflicto: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflicto) from None


# --- Usuarios ---
@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    q = select(Usuario).options(selectinload(Usuario.espacios_asignados)).order_by(Usuario.nombre)
    return [UsuarioOut.of(u) for u in db.scalars(q)]


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(data: UsuarioIn, db: Session = Depends(get_db)):
    user = Usuario(nombre=data.nombre.strip(), correo=data.correo.strip().lower(), password_hash=hash_password(data.password), rol=data.rol)
    db.add(user)
    _commit(db, "Ya existe un usuario con ese correo")
    return UsuarioOut.of(user)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
def editar_usuario(usuario_id: int, data: UsuarioPatch, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    user = _get_or_404(db, Usuario, usuario_id, "Usuario")
    if user.id == admin.id and (data.activo is False or (data.rol is not None and data.rol != admin.rol)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivarte ni cambiar tu propio rol")
    if data.nombre is not None:
        user.nombre = data.nombre.strip()
    if data.rol is not None:
        user.rol = data.rol
    if data.activo is not None:
        user.activo = data.activo
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    db.commit()
    return UsuarioOut.of(user)


# --- Vehículos y colgantes ---
@router.get("/vehiculos", response_model=list[VehiculoOut])
def listar_vehiculos(db: Session = Depends(get_db)):
    return [VehiculoOut.of(v) for v in db.scalars(select(Vehiculo).options(selectinload(Vehiculo.colgante)).order_by(Vehiculo.id))]


@router.post("/vehiculos", response_model=VehiculoOut, status_code=status.HTTP_201_CREATED)
def crear_vehiculo(data: VehiculoIn, db: Session = Depends(get_db)):
    _get_or_404(db, Usuario, data.usuario_id, "Usuario")
    veh = Vehiculo(usuario_id=data.usuario_id, placa=(data.placa or None) and data.placa.strip().upper(), marca=data.marca.strip(), modelo=data.modelo.strip(), color=data.color.strip())
    db.add(veh)
    _commit(db, "Ya existe un vehículo con esa placa")
    return VehiculoOut.of(veh)


@router.get("/colgantes", response_model=list[ColganteAdminOut])
def listar_colgantes(db: Session = Depends(get_db)):
    return [ColganteAdminOut.of(c) for c in db.scalars(select(Colgante).order_by(Colgante.codigo))]


@router.post("/colgantes", response_model=ColganteAdminOut, status_code=status.HTTP_201_CREATED)
def crear_colgante(data: ColganteIn, db: Session = Depends(get_db)):
    if data.vehiculo_id is not None:
        _get_or_404(db, Vehiculo, data.vehiculo_id, "Vehículo")
    col = Colgante(codigo=data.codigo.strip().upper(), tipo=data.tipo, vehiculo_id=data.vehiculo_id)
    db.add(col)
    _commit(db, "El código ya existe o el vehículo ya tiene colgante")
    return ColganteAdminOut.of(col)


@router.patch("/colgantes/{colgante_id}", response_model=ColganteAdminOut)
def editar_colgante(colgante_id: int, data: ColgantePatch, db: Session = Depends(get_db)):
    col = _get_or_404(db, Colgante, colgante_id, "Colgante")
    if "vehiculo_id" in data.model_fields_set:
        if data.vehiculo_id is not None:
            _get_or_404(db, Vehiculo, data.vehiculo_id, "Vehículo")
        col.vehiculo_id = data.vehiculo_id
    if data.tipo is not None:
        col.tipo = data.tipo
    if data.activo is not None:
        col.activo = data.activo
    _commit(db, "Ese vehículo ya tiene un colgante asignado")
    return ColganteAdminOut.of(col)


# --- Espacios (corrección manual y asignación) ---
@router.patch("/espacios/{espacio_id}", response_model=EspacioOut)
def editar_espacio(espacio_id: int, data: EspacioPatch, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    esp = _get_or_404(db, Espacio, espacio_id, "Espacio")
    if "usuario_asignado_id" in data.model_fields_set:
        if data.usuario_asignado_id is not None:
            _get_or_404(db, Usuario, data.usuario_asignado_id, "Usuario")
        esp.usuario_asignado_id = data.usuario_asignado_id
    if data.tipo is not None:
        esp.tipo = data.tipo
    if data.estado is not None and data.estado != esp.estado:
        db.add(Evento(tipo=TipoEvento.cambio_ocupacion, descripcion=f"{admin.correo} cambió {esp.numero}: {esp.estado.value} -> {data.estado.value}", espacio_id=esp.id))
        esp.estado = data.estado
        if data.estado != EstadoEspacio.ocupado:
            esp.colgante_actual_id = None
    db.commit()
    return EspacioOut.of(esp)


# --- Avisos ---
@router.post("/notificaciones", response_model=NotificacionOut, status_code=status.HTTP_201_CREATED)
def crear_notificacion(data: NotificacionIn, db: Session = Depends(get_db)):
    if data.usuario_id is not None:
        _get_or_404(db, Usuario, data.usuario_id, "Usuario")
    n = Notificacion(usuario_id=data.usuario_id, titulo=data.titulo.strip(), mensaje=data.mensaje.strip())
    db.add(n)
    db.commit()
    return NotificacionOut.of(n)

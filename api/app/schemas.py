"""Esquemas de respuesta. Los nombres coinciden con los tipos de mobile/src/types.ts."""
from datetime import datetime

from pydantic import BaseModel, Field

from .models import Camara, Colgante, Espacio, Evento, Notificacion, Usuario, Vehiculo


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    correo: str
    rol: str
    espacioAsignado: str | None = None

    @classmethod
    def of(cls, u: Usuario) -> "UsuarioOut":
        asignado = u.espacios_asignados[0].numero if u.espacios_asignados else None
        return cls(id=u.id, nombre=u.nombre, correo=u.correo, rol=u.rol.value, espacioAsignado=asignado)


class EspacioOut(BaseModel):
    id: int
    numero: str
    zona: str
    tipo: str
    estado: str

    @classmethod
    def of(cls, e: Espacio) -> "EspacioOut":
        return cls(id=e.id, numero=e.numero, zona=e.zona.nombre, tipo=e.tipo.value, estado=e.estado.value)


class ColganteOut(BaseModel):
    codigo: str
    tipo: str


class VehiculoOut(BaseModel):
    id: int
    placa: str | None
    marca: str
    modelo: str
    color: str
    colgante: ColganteOut | None = None

    @classmethod
    def of(cls, v: Vehiculo) -> "VehiculoOut":
        c: Colgante | None = v.colgante
        return cls(id=v.id, placa=v.placa, marca=v.marca, modelo=v.modelo, color=v.color, colgante=ColganteOut(codigo=c.codigo, tipo=c.tipo.value) if c else None)


class NotificacionOut(BaseModel):
    id: int
    titulo: str
    mensaje: str
    fecha: datetime
    leida: bool

    @classmethod
    def of(cls, n: Notificacion) -> "NotificacionOut":
        return cls(id=n.id, titulo=n.titulo, mensaje=n.mensaje, fecha=n.creado_en, leida=n.leida)


class EventoOut(BaseModel):
    id: int
    tipo: str
    descripcion: str
    fecha: datetime

    @classmethod
    def of(cls, e: Evento) -> "EventoOut":
        return cls(id=e.id, tipo=e.tipo.value, descripcion=e.descripcion, fecha=e.creado_en)


class CamaraOut(BaseModel):
    id: int
    camara: str
    zona: str
    estado: str
    ultimaSenal: datetime | None

    @classmethod
    def of(cls, c: Camara) -> "CamaraOut":
        return cls(id=c.id, camara=c.codigo, zona=c.zona.nombre, estado=c.estado.value, ultimaSenal=c.ultima_senal)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Entrada del servidor de visión ---
class EspacioIn(BaseModel):
    numero: str = Field(max_length=20)
    ocupado: bool
    confianza: float | None = Field(default=None, ge=0, le=1)
    colgante_codigo: str | None = Field(default=None, max_length=40)
    colgante_tipo: str | None = Field(default=None, max_length=30)


class OcupacionIn(BaseModel):
    camara: str = Field(max_length=40)
    espacios: list[EspacioIn] = Field(max_length=500)
    baja_confianza: bool = False


class CamaraEstadoIn(BaseModel):
    camara: str = Field(max_length=40)
    en_linea: bool

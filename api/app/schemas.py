"""Esquemas de respuesta. Los nombres coinciden con los tipos de mobile/src/types.ts."""
from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from .models import Camara, Colgante, Espacio, Evento, Notificacion, Rol, TipoColgante, TipoEspacio, EstadoEspacio, Usuario, Vehiculo


def _utc(dt: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; se interpretan como UTC para que la app las convierta bien."""
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


UtcDatetime = Annotated[datetime, AfterValidator(_utc)]


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
    monitoreado: bool = False  # False: ninguna cámara ha reportado este cajón, su estado no es una observación
    actualizado: UtcDatetime | None = None

    @classmethod
    def of(cls, e: Espacio) -> "EspacioOut":
        return cls(id=e.id, numero=e.numero, zona=e.zona.nombre, tipo=e.tipo.value, estado=e.estado.value, monitoreado=bool(e.monitoreado), actualizado=e.actualizado_en)


class ColganteOut(BaseModel):
    codigo: str
    tipo: str


class EventoCajonOut(BaseModel):
    id: int
    tipo: str
    descripcion: str
    fecha: UtcDatetime
    confianza: float | None = None


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
    fecha: UtcDatetime
    leida: bool

    @classmethod
    def of(cls, n: Notificacion) -> "NotificacionOut":
        return cls(id=n.id, titulo=n.titulo, mensaje=n.mensaje, fecha=n.creado_en, leida=n.leida)


class EventoOut(BaseModel):
    id: int
    tipo: str
    descripcion: str
    fecha: UtcDatetime

    @classmethod
    def of(cls, e: Evento) -> "EventoOut":
        return cls(id=e.id, tipo=e.tipo.value, descripcion=e.descripcion, fecha=e.creado_en)


class CamaraOut(BaseModel):
    id: int
    camara: str
    zona: str
    estado: str
    ultimaSenal: UtcDatetime | None

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


class ModeloIn(BaseModel):
    """Estadísticas que reporta el servidor de visión sobre el modelo (para el panel)."""

    camara: str = Field(max_length=40)
    modelo: str = Field(max_length=60)
    dispositivo: str = Field(default="", max_length=40)
    imgsz: int = Field(default=0, ge=0, le=8192)
    fps_video: float = Field(default=0, ge=0, le=1000)
    fps_deteccion: float = Field(default=0, ge=0, le=1000)
    latencia_ms: float = Field(default=0, ge=0, le=600000)
    vehiculos: int = Field(default=0, ge=0, le=10000)
    libres: int = Field(default=0, ge=0, le=10000)
    ocupados: int = Field(default=0, ge=0, le=10000)
    espacios: int = Field(default=0, ge=0, le=10000)
    resolucion: str = Field(default="", max_length=20)
    umbral_confianza: float = Field(default=0, ge=0, le=1)
    ids: list[str] = Field(default_factory=list, max_length=500)  # cajones que vigila esta cámara


class CamaraEstadoIn(BaseModel):
    camara: str = Field(max_length=40)
    en_linea: bool


# --- Administración (solo rol admin) ---
class UsuarioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    correo: str = Field(min_length=5, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    rol: Rol = Rol.estudiante


class UsuarioPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    rol: Rol | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class VehiculoIn(BaseModel):
    usuario_id: int
    placa: str | None = Field(default=None, max_length=20)
    marca: str = Field(min_length=1, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    color: str = Field(min_length=1, max_length=40)


class ColganteIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)
    tipo: TipoColgante
    vehiculo_id: int | None = None


class ColgantePatch(BaseModel):
    vehiculo_id: int | None = None  # None desvincula
    tipo: TipoColgante | None = None
    activo: bool | None = None


class ColganteAdminOut(BaseModel):
    id: int
    codigo: str
    tipo: str
    vehiculoId: int | None
    activo: bool

    @classmethod
    def of(cls, c: Colgante) -> "ColganteAdminOut":
        return cls(id=c.id, codigo=c.codigo, tipo=c.tipo.value, vehiculoId=c.vehiculo_id, activo=c.activo)


class EspacioPatch(BaseModel):
    estado: EstadoEspacio | None = None
    tipo: TipoEspacio | None = None
    usuario_asignado_id: int | None = None  # None desasigna (solo si viene en el cuerpo)


class NotificacionIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    mensaje: str = Field(min_length=1, max_length=1000)
    usuario_id: int | None = None  # None = para todos


class EspacioDetalleOut(EspacioOut):
    camara: str | None = None
    colgante: ColganteOut | None = None  # quién ocupa el cajón ahora (solo administradores)
    historial: list[EventoCajonOut] = []  # últimos eventos del cajón (solo administradores)

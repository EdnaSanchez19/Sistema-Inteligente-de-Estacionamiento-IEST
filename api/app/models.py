"""Modelo de datos (tarea 3.3).

Cadena principal: Usuario -> Vehiculo -> Colgante -> Espacio (ocupación actual).
El historial de entradas/salidas/cambios queda en Evento.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(e: type[enum.Enum]) -> Enum:
    # Se guardan como texto con CHECK: portable entre PostgreSQL/MySQL/SQLite y fácil de migrar.
    return Enum(e, native_enum=False, length=30, create_constraint=True, values_callable=lambda x: [m.value for m in x])


class Rol(str, enum.Enum):
    estudiante = "estudiante"
    docente = "docente"
    directivo = "directivo"
    administrativo = "administrativo"
    externo = "externo"
    admin = "admin"  # permisos de administración del sistema


class EstadoEspacio(str, enum.Enum):
    libre = "libre"
    ocupado = "ocupado"
    reservado = "reservado"
    fuera_de_servicio = "fuera_de_servicio"


class TipoEspacio(str, enum.Enum):
    general = "general"
    discapacidad = "discapacidad"
    directivo = "directivo"
    visitante = "visitante"
    motocicleta = "motocicleta"


class TipoColgante(str, enum.Enum):
    estudiante = "estudiante"
    docente = "docente"
    directivo = "directivo"
    administrativo = "administrativo"
    visitante = "visitante"


class EstadoCamara(str, enum.Enum):
    en_linea = "en_linea"
    desconectada = "desconectada"


class TipoEvento(str, enum.Enum):
    entrada = "entrada"
    salida = "salida"
    cambio_ocupacion = "cambio_ocupacion"
    error_deteccion = "error_deteccion"
    camara_desconectada = "camara_desconectada"
    camara_restablecida = "camara_restablecida"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # nunca la contraseña en claro
    rol: Mapped[Rol] = mapped_column(_enum(Rol), default=Rol.estudiante)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vehiculos: Mapped[list["Vehiculo"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    espacios_asignados: Mapped[list["Espacio"]] = relationship(back_populates="usuario_asignado")


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    placa: Mapped[str | None] = mapped_column(String(20), unique=True)  # opcional: la identificación principal es el colgante
    marca: Mapped[str] = mapped_column(String(60))
    modelo: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(40))

    usuario: Mapped[Usuario] = relationship(back_populates="vehiculos")
    colgante: Mapped["Colgante | None"] = relationship(back_populates="vehiculo", uselist=False)


class Colgante(Base):
    __tablename__ = "colgantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # ID leído por OCR
    tipo: Mapped[TipoColgante] = mapped_column(_enum(TipoColgante))
    vehiculo_id: Mapped[int | None] = mapped_column(ForeignKey("vehiculos.id", ondelete="SET NULL"), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    vehiculo: Mapped[Vehiculo | None] = relationship(back_populates="colgante")


class Zona(Base):
    __tablename__ = "zonas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), unique=True)  # "A", "B", ...
    descripcion: Mapped[str | None] = mapped_column(String(200))

    espacios: Mapped[list["Espacio"]] = relationship(back_populates="zona")
    camaras: Mapped[list["Camara"]] = relationship(back_populates="zona")


class Camara(Base):
    __tablename__ = "camaras"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)  # "CAM-01"; coincide con vision/config/cameras.json
    zona_id: Mapped[int] = mapped_column(ForeignKey("zonas.id"))
    estado: Mapped[EstadoCamara] = mapped_column(_enum(EstadoCamara), default=EstadoCamara.desconectada)
    ultima_senal: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # La URL RTSP (con credenciales) vive solo en la config del servidor de visión, no en la BD.

    zona: Mapped[Zona] = relationship(back_populates="camaras")
    espacios: Mapped[list["Espacio"]] = relationship(back_populates="camara")


class Espacio(Base):
    __tablename__ = "espacios"
    __table_args__ = (UniqueConstraint("zona_id", "numero"), Index("ix_espacios_zona_estado", "zona_id", "estado"))

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20))  # "A-03"
    zona_id: Mapped[int] = mapped_column(ForeignKey("zonas.id"))
    camara_id: Mapped[int | None] = mapped_column(ForeignKey("camaras.id", ondelete="SET NULL"))
    tipo: Mapped[TipoEspacio] = mapped_column(_enum(TipoEspacio), default=TipoEspacio.general)
    estado: Mapped[EstadoEspacio] = mapped_column(_enum(EstadoEspacio), default=EstadoEspacio.libre)
    # Referencia de la ROI para humanos/herramientas; la fuente de verdad de la detección es vision/config.
    roi: Mapped[list | None] = mapped_column(JSON)
    usuario_asignado_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    colgante_actual_id: Mapped[int | None] = mapped_column(ForeignKey("colgantes.id", ondelete="SET NULL"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    zona: Mapped[Zona] = relationship(back_populates="espacios")
    camara: Mapped[Camara | None] = relationship(back_populates="espacios")
    usuario_asignado: Mapped[Usuario | None] = relationship(back_populates="espacios_asignados")
    colgante_actual: Mapped[Colgante | None] = relationship()


class Evento(Base):
    """Historial para auditoría (entradas, salidas, cambios de ocupación, errores)."""

    __tablename__ = "eventos"
    __table_args__ = (Index("ix_eventos_tipo_fecha", "tipo", "creado_en"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoEvento] = mapped_column(_enum(TipoEvento))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    espacio_id: Mapped[int | None] = mapped_column(ForeignKey("espacios.id", ondelete="SET NULL"))
    camara_id: Mapped[int | None] = mapped_column(ForeignKey("camaras.id", ondelete="SET NULL"))
    colgante_id: Mapped[int | None] = mapped_column(ForeignKey("colgantes.id", ondelete="SET NULL"))
    confianza: Mapped[float | None] = mapped_column(Float)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    espacio: Mapped[Espacio | None] = relationship()
    camara: Mapped[Camara | None] = relationship()
    colgante: Mapped[Colgante | None] = relationship()


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)  # NULL = para todos
    titulo: Mapped[str] = mapped_column(String(120))
    mensaje: Mapped[str] = mapped_column(Text)
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

"""Reglas de alerta para el operador.

Cada regla mira el estado actual de la base de datos y dice qué condiciones se cumplen ahora mismo; `evaluar` las compara
con las alertas activas: crea las que faltan y cierra las que ya no se cumplen. Así una alerta no se repite mientras la
condición sigue, y se cierra sola cuando termina (el coche se va, retiran el objeto, vuelve la cámara).

Reglas:
  estancia_excedida        un coche lleva en el mismo cajón más del límite (uno más corto para los cajones de visitante)
  obstruccion_prolongada   un cajón lleva obstruido más del límite
  camara_sin_senal         una cámara está desconectada
  ocupacion_alta           los cajones monitoreados están casi todos ocupados

Para agregar una regla: una función que reciba (db, reglas, ahora, activas) y devuelva `Condicion`, y sumarla a `REGLAS`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alerta, Camara, Espacio, EstadoCamara, EstadoEspacio, TipoEspacio, Zona
from .tiempo import _utc, formatear, segundos_desde

ESTANCIA, OBSTRUCCION, CAMARA, OCUPACION = "estancia_excedida", "obstruccion_prolongada", "camara_sin_senal", "ocupacion_alta"
MARGEN_OCUPACION = 5  # puntos que tiene que bajar la ocupación para cerrar la alerta (que no parpadee en el umbral)
MINIMO_PARA_OCUPACION = 10  # con menos cajones monitoreados que esto, "casi lleno" no significa nada


@dataclass(frozen=True)
class Reglas:
    """Límites de cada regla. 0 apaga la regla."""

    estancia_min: int = 720
    estancia_visitante_min: int = 180
    obstruccion_min: int = 15
    ocupacion_pct: int = 95

    @classmethod
    def de_ajustes(cls, s) -> "Reglas":
        return cls(s.alerta_estancia_min, s.alerta_estancia_visitante_min, s.alerta_obstruccion_min, s.alerta_ocupacion_pct)


@dataclass(frozen=True)
class Condicion:
    tipo: str
    clave: str
    mensaje: str
    espacio_id: int | None = None
    camara_id: int | None = None


def _espacios_con_camara_en_linea(db: Session, estado: EstadoEspacio):
    """Cajones monitoreados en `estado` cuya cámara reporta: si la cámara está caída, su estado es viejo y no se juzga."""
    q = (select(Espacio, Zona).join(Zona, Espacio.zona_id == Zona.id).join(Camara, Espacio.camara_id == Camara.id)
         .where(Espacio.monitoreado.is_(True), Espacio.estado == estado, Espacio.estado_desde.is_not(None), Camara.estado == EstadoCamara.en_linea))
    return db.execute(q).all()


def _estancias(db: Session, reglas: Reglas, ahora: datetime, activas: set[str]) -> list[Condicion]:
    if not reglas.estancia_min and not reglas.estancia_visitante_min:
        return []
    salida = []
    for esp, zona in _espacios_con_camara_en_linea(db, EstadoEspacio.ocupado):
        limite = reglas.estancia_visitante_min if esp.tipo == TipoEspacio.visitante else reglas.estancia_min
        segundos = segundos_desde(esp.estado_desde, ahora) or 0
        if limite and segundos >= limite * 60:
            cuanto = "más de" if esp.inicio_observado else "al menos"  # si la cámara no vio llegar al coche, es un mínimo
            salida.append(Condicion(ESTANCIA, f"estancia:{esp.id}", f"{esp.numero} ({zona.rotulo}): el vehículo lleva {cuanto} {formatear(limite * 60)} en el cajón", espacio_id=esp.id))
    return salida


def _obstrucciones(db: Session, reglas: Reglas, ahora: datetime, activas: set[str]) -> list[Condicion]:
    if not reglas.obstruccion_min:
        return []
    salida = []
    for esp, zona in _espacios_con_camara_en_linea(db, EstadoEspacio.obstruido):
        if (segundos_desde(esp.estado_desde, ahora) or 0) >= reglas.obstruccion_min * 60:
            salida.append(Condicion(OBSTRUCCION, f"obstruccion:{esp.id}", f"{esp.numero} ({zona.rotulo}): obstruido por {esp.objeto or 'un objeto'} desde hace más de {formatear(reglas.obstruccion_min * 60)}", espacio_id=esp.id))
    return salida


def _camaras(db: Session, reglas: Reglas, ahora: datetime, activas: set[str]) -> list[Condicion]:
    # una cámara que nunca ha enviado nada no está "caída": todavía no se conecta (instalación a medias)
    q = select(Camara).where(Camara.estado == EstadoCamara.desconectada, Camara.ultima_senal.is_not(None))
    return [Condicion(CAMARA, f"camara:{c.id}", f"{c.codigo}{f' ({c.nombre})' if c.nombre else ''} sin señal: sus cajones no se están actualizando", camara_id=c.id) for c in db.scalars(q)]


def _ocupacion(db: Session, reglas: Reglas, ahora: datetime, activas: set[str]) -> list[Condicion]:
    if not reglas.ocupacion_pct:
        return []
    estados = db.scalars(select(Espacio.estado).join(Camara, Espacio.camara_id == Camara.id).where(Espacio.monitoreado.is_(True), Camara.estado == EstadoCamara.en_linea)).all()
    if len(estados) < MINIMO_PARA_OCUPACION:
        return []
    pct = 100 * sum(e == EstadoEspacio.ocupado for e in estados) / len(estados)
    clave = "ocupacion:global"
    umbral = reglas.ocupacion_pct - (MARGEN_OCUPACION if clave in activas else 0)
    return [Condicion(OCUPACION, clave, f"El estacionamiento está al {reglas.ocupacion_pct} % o más: quedan pocos cajones libres")] if pct >= umbral else []


REGLAS = (_estancias, _obstrucciones, _camaras, _ocupacion)


def _sin_datos(db: Session) -> set[int]:
    """Cajones cuya cámara está caída: sus alertas se quedan como están hasta que la cámara vuelva."""
    return set(db.scalars(select(Espacio.id).join(Camara, Espacio.camara_id == Camara.id).where(Camara.estado == EstadoCamara.desconectada)))


def evaluar(db: Session, reglas: Reglas | None = None, ahora: datetime | None = None) -> tuple[int, int]:
    """Crea las alertas nuevas y cierra las que ya no se cumplen. Devuelve (creadas, cerradas)."""
    from .config import get_settings

    reglas = reglas or Reglas.de_ajustes(get_settings())
    ahora = _utc(ahora) if ahora else datetime.now(timezone.utc)
    activas = {a.clave: a for a in db.scalars(select(Alerta).where(Alerta.activa.is_(True)))}
    vigentes = {c.clave: c for regla in REGLAS for c in regla(db, reglas, ahora, set(activas))}
    congelados = _sin_datos(db)

    creadas = cerradas = 0
    for clave, c in vigentes.items():
        if clave not in activas:
            db.add(Alerta(tipo=c.tipo, clave=clave, mensaje=c.mensaje, espacio_id=c.espacio_id, camara_id=c.camara_id, creada_en=ahora))
            creadas += 1
    for clave, alerta in activas.items():
        if clave in vigentes or (alerta.espacio_id is not None and alerta.espacio_id in congelados):
            continue
        alerta.activa, alerta.resuelta_en = False, ahora
        cerradas += 1
    if creadas or cerradas:
        db.commit()
    return creadas, cerradas


def purgar(db: Session, dias: int, ahora: datetime | None = None) -> int:
    """Borra las alertas cerradas hace más de `dias` (las activas nunca)."""
    limite = (ahora or datetime.now(timezone.utc)) - timedelta(days=dias)
    viejas = list(db.scalars(select(Alerta).where(Alerta.activa.is_(False), Alerta.resuelta_en < limite)))
    for a in viejas:
        db.delete(a)
    if viejas:
        db.commit()
    return len(viejas)

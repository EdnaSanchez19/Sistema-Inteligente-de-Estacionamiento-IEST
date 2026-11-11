"""Serie histórica de ocupación y lo que se calcula con ella (ocupación por hora o por día, horas pico) y exportación a CSV.

La serie se guarda en la tabla `muestras_ocupacion`: una fila por zona cada pocos minutos, solo con los cajones que una
cámara en línea está observando. Si no hay cámaras reportando no se guarda nada: un hueco en la serie es más honesto que
repetir el último estado conocido.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import Alerta, Camara, Espacio, EstadoCamara, EstadoEspacio, Evento, MuestraOcupacion, Zona
from .tiempo import _utc, a_local, segundos_desde

MAX_FILAS_CSV = 200_000


# --- Guardar ---
def guardar_muestra(db: Session, ahora: datetime | None = None) -> int:
    """Guarda la ocupación actual por zona. Devuelve cuántas zonas se guardaron."""
    ahora = ahora or datetime.now(timezone.utc)
    q = (select(Espacio.zona_id, Espacio.estado, func.count()).join(Camara, Espacio.camara_id == Camara.id)
         .where(Espacio.monitoreado.is_(True), Camara.estado == EstadoCamara.en_linea).group_by(Espacio.zona_id, Espacio.estado))
    por_zona: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    for zona_id, estado, n in db.execute(q).all():
        por_zona[zona_id][estado] += n
    for zona_id, cuenta in por_zona.items():
        db.add(MuestraOcupacion(tomada_en=ahora, zona_id=zona_id, libres=cuenta[EstadoEspacio.libre], ocupados=cuenta[EstadoEspacio.ocupado],
                                obstruidos=cuenta[EstadoEspacio.obstruido], monitoreados=sum(cuenta.values())))
    if por_zona:
        db.commit()
    return len(por_zona)


def purgar_muestras(db: Session, dias: int, ahora: datetime | None = None) -> int:
    limite = (ahora or datetime.now(timezone.utc)) - timedelta(days=dias)
    borradas = db.execute(delete(MuestraOcupacion).where(MuestraOcupacion.tomada_en < limite)).rowcount or 0
    db.commit()
    return borradas


# --- Leer y agrupar ---
def puntos(db: Session, desde: datetime, hasta: datetime, zona: str | None = None) -> list[dict]:
    """La serie entre dos fechas: un punto por instante, sumando las zonas (o solo la zona pedida)."""
    q = (select(MuestraOcupacion.tomada_en, func.sum(MuestraOcupacion.libres), func.sum(MuestraOcupacion.ocupados), func.sum(MuestraOcupacion.obstruidos), func.sum(MuestraOcupacion.monitoreados))
         .where(MuestraOcupacion.tomada_en >= desde, MuestraOcupacion.tomada_en < hasta).group_by(MuestraOcupacion.tomada_en).order_by(MuestraOcupacion.tomada_en))
    if zona:
        q = q.join(Zona, MuestraOcupacion.zona_id == Zona.id).where(Zona.nombre == zona)
    return [{"t": _utc(t), "libres": int(li), "ocupados": int(oc), "obstruidos": int(ob), "monitoreados": int(mo)} for t, li, oc, ob, mo in db.execute(q).all()]


def _pct(p: dict) -> float:
    return 100 * p["ocupados"] / p["monitoreados"] if p["monitoreados"] else 0.0


def _resumir(grupo: list[dict]) -> dict:
    pcts = [_pct(p) for p in grupo]
    return {
        "ocupacion_media_pct": round(sum(pcts) / len(pcts), 1), "ocupacion_max_pct": round(max(pcts), 1),
        "ocupados_media": round(sum(p["ocupados"] for p in grupo) / len(grupo), 1), "ocupados_max": max(p["ocupados"] for p in grupo),
        "libres_min": min(p["libres"] for p in grupo), "monitoreados": max(p["monitoreados"] for p in grupo), "muestras": len(grupo),
    }


def por_intervalo(serie: list[dict], intervalo: str, utc_offset_h: int) -> list[dict]:
    """Agrupa la serie por hora o por día (hora local). Cada grupo: ocupación media y máxima, mínimo de libres."""
    formato = "%Y-%m-%dT%H:00" if intervalo == "hora" else "%Y-%m-%d"
    grupos: dict[str, list[dict]] = defaultdict(list)
    for p in serie:
        grupos[a_local(p["t"], utc_offset_h).strftime(formato)].append(p)
    return [{"inicio": inicio, **_resumir(g)} for inicio, g in sorted(grupos.items())]


def horas_pico(serie: list[dict], utc_offset_h: int) -> list[dict]:
    """Las 24 horas del día con su ocupación media y máxima en el periodo (las horas sin datos traen `muestras` 0)."""
    grupos: dict[int, list[dict]] = defaultdict(list)
    for p in serie:
        grupos[a_local(p["t"], utc_offset_h).hour].append(p)
    vacio = {"ocupacion_media_pct": None, "ocupacion_max_pct": None, "ocupados_media": None, "ocupados_max": None, "libres_min": None, "monitoreados": 0, "muestras": 0}
    return [{"hora": h, **(_resumir(grupos[h]) if grupos.get(h) else vacio)} for h in range(24)]


def mapa_semanal(serie: list[dict], utc_offset_h: int) -> list[dict]:
    """Ocupación media por día de la semana (0 = lunes) y hora: la cuadrícula de 7 x 24 del mapa de calor."""
    grupos: dict[tuple[int, int], list[float]] = defaultdict(list)
    for p in serie:
        local = a_local(p["t"], utc_offset_h)
        grupos[(local.weekday(), local.hour)].append(_pct(p))
    return [{"dia": d, "hora": h, "ocupacion_media_pct": round(sum(v) / len(v), 1), "muestras": len(v)} for (d, h), v in sorted(grupos.items())]


def resumen(db: Session, desde: datetime, hasta: datetime, utc_offset_h: int) -> dict:
    serie = puntos(db, desde, hasta)
    eventos = {tipo.value: n for tipo, n in db.execute(select(Evento.tipo, func.count()).where(Evento.creado_en >= desde, Evento.creado_en < hasta).group_by(Evento.tipo)).all()}
    pico = max(serie, key=_pct) if serie else None
    horas = [h for h in horas_pico(serie, utc_offset_h) if h["muestras"]]
    hora_pico = max(horas, key=lambda h: h["ocupacion_media_pct"]) if horas else None
    return {
        "muestras": len(serie),
        "ocupacion_media_pct": round(sum(_pct(p) for p in serie) / len(serie), 1) if serie else None,
        "pico": {"ocupacion_pct": round(_pct(pico), 1), "ocupados": pico["ocupados"], "monitoreados": pico["monitoreados"], "cuando": pico["t"]} if pico else None,
        "hora_pico": {"hora": hora_pico["hora"], "ocupacion_media_pct": hora_pico["ocupacion_media_pct"]} if hora_pico else None,
        "entradas": eventos.get("entrada", 0), "salidas": eventos.get("salida", 0), "obstrucciones": eventos.get("obstruccion", 0),
        "caidas_de_camara": eventos.get("camara_desconectada", 0),
        "alertas": db.scalar(select(func.count()).select_from(Alerta).where(Alerta.creada_en >= desde, Alerta.creada_en < hasta)) or 0,
    }


# --- CSV ---
def _celda(valor) -> str:
    """Texto de una celda. Lo que empieza con = + - @ lleva un apóstrofo delante: Excel lo ejecutaría como fórmula."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def a_csv(encabezados: list[str], filas) -> str:
    """CSV con BOM (para que Excel lea bien los acentos)."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(encabezados)
    for fila in filas:
        escritor.writerow([_celda(v) for v in fila])
    return "﻿" + salida.getvalue()


def _fecha(d: datetime | None, utc_offset_h: int) -> str:
    return a_local(d, utc_offset_h).strftime("%Y-%m-%d %H:%M:%S") if d else ""


def csv_ocupacion(db: Session, desde: datetime, hasta: datetime, utc_offset_h: int) -> str:
    q = (select(MuestraOcupacion, Zona).join(Zona, MuestraOcupacion.zona_id == Zona.id).where(MuestraOcupacion.tomada_en >= desde, MuestraOcupacion.tomada_en < hasta)
         .order_by(MuestraOcupacion.tomada_en, Zona.nombre).limit(MAX_FILAS_CSV))
    filas = ([_fecha(m.tomada_en, utc_offset_h), z.rotulo, m.libres, m.ocupados, m.obstruidos, m.monitoreados, round(100 * m.ocupados / m.monitoreados, 1) if m.monitoreados else 0]
             for m, z in db.execute(q).all())
    return a_csv(["fecha", "zona", "libres", "ocupados", "obstruidos", "monitoreados", "ocupacion_pct"], filas)


def csv_eventos(db: Session, desde: datetime, hasta: datetime, utc_offset_h: int) -> str:
    q = (select(Evento, Espacio.numero, Camara.codigo).outerjoin(Espacio, Evento.espacio_id == Espacio.id).outerjoin(Camara, Evento.camara_id == Camara.id)
         .where(Evento.creado_en >= desde, Evento.creado_en < hasta).order_by(Evento.creado_en).limit(MAX_FILAS_CSV))
    filas = ([_fecha(e.creado_en, utc_offset_h), e.tipo.value, e.descripcion, numero, camara, "" if e.confianza is None else round(e.confianza, 2)] for e, numero, camara in db.execute(q).all())
    return a_csv(["fecha", "tipo", "descripcion", "cajon", "camara", "confianza"], filas)


def csv_estancias(db: Session, utc_offset_h: int, ahora: datetime | None = None) -> str:
    """El estado de cada cajón monitoreado ahora mismo y cuánto lleva así."""
    q = select(Espacio, Zona).join(Zona, Espacio.zona_id == Zona.id).where(Espacio.monitoreado.is_(True)).order_by(Zona.nombre, Espacio.numero)
    filas = []
    for e, z in db.execute(q).all():
        segundos = segundos_desde(e.estado_desde, ahora)
        filas.append([e.numero, z.rotulo, e.tipo.value, e.estado.value, _fecha(e.estado_desde, utc_offset_h), "" if segundos is None else round(segundos / 60, 1),
                      "" if segundos is None else "exacta" if e.inicio_observado else "al menos", e.objeto if e.estado == EstadoEspacio.obstruido else ""])
    return a_csv(["cajon", "zona", "tipo", "estado", "desde", "minutos", "duracion", "objeto"], filas)


def csv_alertas(db: Session, desde: datetime, hasta: datetime, utc_offset_h: int) -> str:
    q = (select(Alerta, Espacio.numero, Camara.codigo).outerjoin(Espacio, Alerta.espacio_id == Espacio.id).outerjoin(Camara, Alerta.camara_id == Camara.id)
         .where(Alerta.creada_en >= desde, Alerta.creada_en < hasta).order_by(Alerta.creada_en).limit(MAX_FILAS_CSV))
    filas = ([_fecha(a.creada_en, utc_offset_h), a.tipo, a.mensaje, numero, camara, "activa" if a.activa else "resuelta", _fecha(a.atendida_en, utc_offset_h), _fecha(a.resuelta_en, utc_offset_h)]
             for a, numero, camara in db.execute(q).all())
    return a_csv(["creada", "tipo", "mensaje", "cajon", "camara", "estado", "atendida", "resuelta"], filas)

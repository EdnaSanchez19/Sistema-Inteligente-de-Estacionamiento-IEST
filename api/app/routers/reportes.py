"""Reportes para el administrador: ocupación histórica, horas pico y exportación a CSV."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from .. import reportes
from ..auth import require_admin
from ..config import get_settings
from ..db import get_db
from ..tiempo import a_local, de_local

router = APIRouter(prefix="/reportes", tags=["reportes"], dependencies=[Depends(require_admin)])

MAX_DIAS = 366


def periodo(desde: date | None = Query(None, description="Primer día (hora local). Por defecto, hace 7 días."),
            hasta: date | None = Query(None, description="Último día, incluido (hora local). Por defecto, hoy.")) -> tuple[datetime, datetime]:
    """El periodo pedido, en UTC: desde las 00:00 del primer día hasta las 24:00 del último."""
    offset = get_settings().utc_offset_h
    hoy = a_local(datetime.now(timezone.utc), offset).date()
    hasta = hasta or hoy
    desde = desde or hasta - timedelta(days=6)
    if desde > hasta:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "`desde` no puede ser posterior a `hasta`")
    if (hasta - desde).days >= MAX_DIAS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"El periodo no puede pasar de {MAX_DIAS} días")
    inicio = datetime(desde.year, desde.month, desde.day)
    fin = datetime(hasta.year, hasta.month, hasta.day) + timedelta(days=1)
    return de_local(inicio, offset), de_local(fin, offset)


@router.get("/resumen")
def resumen(p: tuple[datetime, datetime] = Depends(periodo), db: Session = Depends(get_db)) -> dict:
    """Ocupación media, el momento y la hora de mayor ocupación, entradas, salidas y alertas del periodo."""
    return {"desde": p[0], "hasta": p[1], **reportes.resumen(db, *p, get_settings().utc_offset_h)}


@router.get("/ocupacion")
def ocupacion(intervalo: Literal["hora", "dia"] = "hora", zona: str | None = Query(None, max_length=40), p: tuple[datetime, datetime] = Depends(periodo), db: Session = Depends(get_db)) -> list[dict]:
    """Ocupación media y máxima por hora o por día (hora local)."""
    return reportes.por_intervalo(reportes.puntos(db, *p, zona), intervalo, get_settings().utc_offset_h)


@router.get("/horas-pico")
def horas_pico(zona: str | None = Query(None, max_length=40), p: tuple[datetime, datetime] = Depends(periodo), db: Session = Depends(get_db)) -> dict:
    """Ocupación por hora del día (24 valores) y por día de la semana y hora (mapa de calor)."""
    serie, offset = reportes.puntos(db, *p, zona), get_settings().utc_offset_h
    return {"por_hora": reportes.horas_pico(serie, offset), "semana": reportes.mapa_semanal(serie, offset)}


@router.get("/exportar/{conjunto}")
def exportar(conjunto: Literal["ocupacion", "eventos", "estancias", "alertas"], p: tuple[datetime, datetime] = Depends(periodo), db: Session = Depends(get_db)) -> Response:
    """Descarga en CSV (se abre en Excel): la serie de ocupación, los eventos, las alertas o el estado actual de cada cajón."""
    offset = get_settings().utc_offset_h
    if conjunto == "ocupacion":
        cuerpo = reportes.csv_ocupacion(db, *p, offset)
    elif conjunto == "eventos":
        cuerpo = reportes.csv_eventos(db, *p, offset)
    elif conjunto == "alertas":
        cuerpo = reportes.csv_alertas(db, *p, offset)
    else:
        cuerpo = reportes.csv_estancias(db, offset)
    nombre = f"{conjunto}_{a_local(datetime.now(timezone.utc), offset):%Y%m%d_%H%M}.csv"
    return Response(cuerpo, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"})

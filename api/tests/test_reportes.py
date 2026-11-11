"""Reportes: la serie de ocupación guardada en la base de datos, su agrupación por hora y la exportación a CSV."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app import reportes
from app.db import get_db
from app.main import app
from app.models import MuestraOcupacion
from helpers import ADMIN, DEMO, KEY, login

OFFSET = -6  # hora local del campus


def sesion():
    return next(app.dependency_overrides[get_db]())


def reportar(client, camara, ocupados, libres):
    espacios = [{"numero": n, "ocupado": True} for n in ocupados] + [{"numero": n, "ocupado": False} for n in libres]
    assert client.post("/ingest/ocupacion", headers=KEY, json={"camara": camara, "espacios": espacios}).status_code == 200


def punto(hora_local, ocupados, monitoreados=10, dia=2):
    """Un punto de la serie a una hora local del lunes 2 de noviembre de 2026 (u otro día del mes)."""
    t = datetime(2026, 11, dia, hora_local, 30) - timedelta(hours=OFFSET)
    return {"t": t.replace(tzinfo=timezone.utc), "libres": monitoreados - ocupados, "ocupados": ocupados, "obstruidos": 0, "monitoreados": monitoreados}


def test_sin_camaras_en_linea_no_se_guarda_nada(client):
    db = sesion()
    assert reportes.guardar_muestra(db) == 0
    assert db.scalar(select(func.count()).select_from(MuestraOcupacion)) == 0


def test_se_guarda_una_fila_por_zona_con_lo_que_ven_las_camaras(client):
    db = sesion()
    reportar(client, "CAM-02", ["C-01", "C-02", "D-01"], ["C-03", "D-02"])
    reportar(client, "CAM-01", ["A-01"], [])
    assert reportes.guardar_muestra(db) == 3  # filas 1, 3 y 4
    filas = {m.zona.nombre: m for m in db.scalars(select(MuestraOcupacion))}
    assert (filas["C"].ocupados, filas["C"].libres, filas["C"].monitoreados) == (2, 1, 3)
    assert (filas["D"].ocupados, filas["D"].libres) == (1, 1) and filas["A"].ocupados == 1

    # una cámara caída deja de aportar: sus cajones tienen un estado viejo
    client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-01", "en_linea": False})
    assert reportes.guardar_muestra(db) == 2


def test_agrupar_por_hora_por_dia_y_horas_pico():
    serie = [punto(8, 2), punto(8, 4), punto(11, 9), punto(11, 10), punto(23, 1), punto(9, 5, dia=3)]
    por_hora = reportes.por_intervalo(serie, "hora", OFFSET)
    assert [g["inicio"] for g in por_hora] == ["2026-11-02T08:00", "2026-11-02T11:00", "2026-11-02T23:00", "2026-11-03T09:00"]  # en hora local, no en UTC
    assert por_hora[0] == {"inicio": "2026-11-02T08:00", "ocupacion_media_pct": 30.0, "ocupacion_max_pct": 40.0, "ocupados_media": 3.0, "ocupados_max": 4, "libres_min": 6, "monitoreados": 10, "muestras": 2}
    por_dia = reportes.por_intervalo(serie, "dia", OFFSET)
    assert [(g["inicio"], g["muestras"]) for g in por_dia] == [("2026-11-02", 5), ("2026-11-03", 1)]

    horas = reportes.horas_pico(serie, OFFSET)
    assert len(horas) == 24 and horas[11]["ocupacion_media_pct"] == 95.0 and horas[3]["muestras"] == 0 and horas[3]["ocupacion_media_pct"] is None
    semana = {(c["dia"], c["hora"]): c["ocupacion_media_pct"] for c in reportes.mapa_semanal(serie, OFFSET)}
    assert semana[(0, 11)] == 95.0 and semana[(1, 9)] == 50.0  # lunes a las 11 y martes a las 9
    assert reportes.por_intervalo([], "hora", OFFSET) == []


def test_reportes_por_la_api_solo_para_administradores(client):
    db = sesion()
    admin, demo = login(client, *ADMIN), login(client, *DEMO)
    assert client.get("/reportes/resumen").status_code == 401
    assert client.get("/reportes/resumen", headers=demo).status_code == 403

    vacio = client.get("/reportes/resumen", headers=admin).json()
    assert vacio["muestras"] == 0 and vacio["ocupacion_media_pct"] is None and vacio["pico"] is None

    ahora = datetime.now(timezone.utc)
    reportar(client, "CAM-02", ["C-01"], ["C-02", "C-03", "C-04"])
    reportes.guardar_muestra(db, ahora - timedelta(minutes=10))  # 25 %
    reportar(client, "CAM-02", ["C-02", "C-03"], [])  # dos entradas
    reportes.guardar_muestra(db, ahora - timedelta(minutes=5))  # 75 %

    r = client.get("/reportes/resumen", headers=admin).json()
    assert r["muestras"] == 2 and r["ocupacion_media_pct"] == 50.0 and r["pico"]["ocupacion_pct"] == 75.0 and r["pico"]["ocupados"] == 3 and r["entradas"] == 2
    por_dia = client.get("/reportes/ocupacion?intervalo=dia", headers=admin).json()
    assert sum(g["muestras"] for g in por_dia) == 2
    assert client.get("/reportes/ocupacion?zona=A", headers=admin).json() == []  # la fila 1 no tiene muestras
    pico = client.get("/reportes/horas-pico", headers=admin).json()
    assert len(pico["por_hora"]) == 24 and sum(h["muestras"] for h in pico["por_hora"]) == 2 and pico["semana"]

    assert client.get("/reportes/ocupacion?desde=2026-02-01&hasta=2026-01-01", headers=admin).status_code == 422
    assert client.get("/reportes/ocupacion?desde=2020-01-01", headers=admin).status_code == 422  # más de un año


def test_exportar_a_csv(client):
    db = sesion()
    admin = login(client, *ADMIN)
    reportar(client, "CAM-02", ["C-01"], ["C-02"])
    reportar(client, "CAM-02", ["C-02"], [])
    reportes.guardar_muestra(db)

    r = client.get("/reportes/exportar/ocupacion", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    lineas = r.text.lstrip("﻿").strip().split("\r\n")
    assert r.text.startswith("﻿") and lineas[0] == "fecha,zona,libres,ocupados,obstruidos,monitoreados,ocupacion_pct" and lineas[1].endswith(",Fila 3,0,2,0,2,100.0")

    eventos = client.get("/reportes/exportar/eventos", headers=admin).text
    assert "entrada,Entrada en C-02: vehículo sin colgante identificado,C-02,CAM-02" in eventos
    estancias = client.get("/reportes/exportar/estancias", headers=admin).text
    assert "C-01,Fila 3,visitante,ocupado," in estancias and ",al menos," in estancias and ",exacta," in estancias
    assert client.get("/reportes/exportar/alertas", headers=admin).text.strip().endswith("creada,tipo,mensaje,cajon,camara,estado,atendida,resuelta")
    assert client.get("/reportes/exportar/usuarios", headers=admin).status_code == 422
    assert client.get("/reportes/exportar/eventos", headers=login(client, *DEMO)).status_code == 403


def test_el_csv_no_deja_pasar_formulas():
    texto = reportes.a_csv(["a", "b"], [["=HYPERLINK(\"http://x\")", "normal"], ["-5", None], [3, "@cmd"]])
    assert texto.split("\r\n")[1:4] == ["\"'=HYPERLINK(\"\"http://x\"\")\",normal", "'-5,", "3,'@cmd"]


def test_las_muestras_viejas_se_purgan(client):
    db = sesion()
    reportar(client, "CAM-02", ["C-01"], [])
    ahora = datetime.now(timezone.utc)
    reportes.guardar_muestra(db, ahora - timedelta(days=400))
    reportes.guardar_muestra(db, ahora)
    assert reportes.purgar_muestras(db, 365) == 1
    assert db.scalar(select(func.count()).select_from(MuestraOcupacion)) == 1


def test_el_modelo_reporta_luz_errores_y_espera(client):
    from app import estado_vision

    estado_vision.limpiar()
    base = {"camara": "CAM-01", "modelo": "YOLOv8n + YOLOv8s"}
    assert client.post("/ingest/modelo", headers=KEY, json={**base, "luz": "oscuro", "errores": 2, "espera_gpu_ms": 41.5}).status_code == 200
    v = client.get("/sistema/estado", headers=login(client, *DEMO)).json()["vision"][0]
    assert (v["luz"], v["errores"], v["espera_gpu_ms"]) == ("oscuro", 2, 41.5)
    assert client.post("/ingest/modelo", headers=KEY, json={**base, "luz": "raro"}).status_code == 422
    estado_vision.limpiar()

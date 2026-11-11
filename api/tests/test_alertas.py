"""Alertas para el operador: se crean cuando la condición se cumple, no se repiten y se cierran solas."""
from datetime import timedelta

from sqlalchemy import select

from app import alertas
from app.alertas import Reglas
from app.db import get_db
from app.main import app
from app.models import Alerta, Espacio, utcnow
from helpers import ADMIN, DEMO, KEY, login

REGLAS = Reglas(estancia_min=720, estancia_visitante_min=180, obstruccion_min=15, ocupacion_pct=95)


def sesion():
    """La misma base en memoria que usa el cliente de la prueba."""
    return next(app.dependency_overrides[get_db]())


def reportar(client, camara, espacios):
    r = client.post("/ingest/ocupacion", headers=KEY, json={"camara": camara, "espacios": espacios})
    assert r.status_code == 200


def atrasar(db, numero, minutos):
    """Hace como si el cajón llevara `minutos` en su estado actual."""
    esp = db.scalar(select(Espacio).where(Espacio.numero == numero))
    esp.estado_desde = utcnow() - timedelta(minutes=minutos)
    db.commit()


def activas(db):
    db.expire_all()
    return {a.clave: a for a in db.scalars(select(Alerta).where(Alerta.activa.is_(True)))}


def test_estancia_excedida_se_crea_una_vez_y_se_cierra_cuando_el_coche_se_va(client):
    db = sesion()
    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": True}, {"numero": "C-05", "ocupado": True}, {"numero": "C-06", "ocupado": False}])
    assert alertas.evaluar(db, REGLAS) == (0, 0)  # acaban de llegar

    atrasar(db, "C-01", 240)  # cajón de visitante: límite de 3 h
    atrasar(db, "C-05", 240)  # cajón general: límite de 12 h
    assert alertas.evaluar(db, REGLAS) == (1, 0)
    (alerta,) = activas(db).values()
    assert alerta.tipo == alertas.ESTANCIA and "C-01" in alerta.mensaje and "al menos 3 h" in alerta.mensaje  # la cámara no vio llegar al coche
    assert alertas.evaluar(db, REGLAS) == (0, 0)  # la misma condición no genera otra alerta

    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": False}])
    assert alertas.evaluar(db, REGLAS) == (0, 1)
    db.expire_all()
    cerrada = db.scalar(select(Alerta))
    assert cerrada.activa is False and cerrada.resuelta_en is not None


def test_obstruccion_prolongada_y_regla_apagada(client):
    db = sesion()
    reportar(client, "CAM-02", [{"numero": "D-04", "ocupado": False, "estado": "obstruido", "objeto": "maleta"}])
    atrasar(db, "D-04", 20)
    assert alertas.evaluar(db, Reglas(obstruccion_min=0)) == (0, 0)  # 0 apaga la regla
    assert alertas.evaluar(db, REGLAS) == (1, 0)
    (alerta,) = activas(db).values()
    assert alerta.tipo == alertas.OBSTRUCCION and "maleta" in alerta.mensaje


def test_con_la_camara_caida_se_avisa_de_la_camara_y_sus_alertas_no_se_tocan(client):
    db = sesion()
    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": True}, {"numero": "C-02", "ocupado": True}])
    atrasar(db, "C-01", 240)
    assert alertas.evaluar(db, REGLAS) == (1, 0)

    assert client.post("/ingest/camara-estado", headers=KEY, json={"camara": "CAM-02", "en_linea": False}).status_code == 200
    atrasar(db, "C-02", 240)  # con la cámara caída este estado es viejo: no se juzga
    assert alertas.evaluar(db, REGLAS) == (1, 0)  # solo la de la cámara
    tipos = sorted(a.tipo for a in activas(db).values())
    assert tipos == [alertas.CAMARA, alertas.ESTANCIA]  # la de C-01 sigue abierta: no se sabe si el coche se fue

    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": True}, {"numero": "C-02", "ocupado": True}])  # vuelve la señal
    assert alertas.evaluar(db, REGLAS) == (1, 1)  # se cierra la de la cámara y ahora sí cuenta C-02
    assert sorted(a.tipo for a in activas(db).values()) == [alertas.ESTANCIA, alertas.ESTANCIA]


def test_una_camara_que_nunca_se_conecto_no_es_una_alerta(client):
    assert alertas.evaluar(sesion(), REGLAS) == (0, 0)  # las 3 cámaras empiezan desconectadas y sin señal previa


def test_ocupacion_alta_no_parpadea_en_el_umbral(client):
    db = sesion()
    numeros = [f"C-{i:02d}" for i in range(1, 21)]
    reportar(client, "CAM-02", [{"numero": n, "ocupado": True} for n in numeros])
    assert alertas.evaluar(db, REGLAS) == (1, 0)
    assert next(iter(activas(db).values())).tipo == alertas.OCUPACION

    reportar(client, "CAM-02", [{"numero": "C-20", "ocupado": False}, {"numero": "C-19", "ocupado": False}])  # 90 %: dentro del margen
    assert alertas.evaluar(db, REGLAS) == (0, 0)
    reportar(client, "CAM-02", [{"numero": "C-18", "ocupado": False}])  # 85 %
    assert alertas.evaluar(db, REGLAS) == (0, 1)
    assert alertas.evaluar(db, REGLAS) == (0, 0)  # y al 85 % no se vuelve a abrir


def test_el_administrador_ve_y_atiende_las_alertas(client):
    db = sesion()
    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": True}])
    atrasar(db, "C-01", 120)
    admin, demo = login(client, *ADMIN), login(client, *DEMO)

    assert client.get("/alertas").status_code == 401
    assert client.get("/alertas", headers=demo).status_code == 403
    assert client.get("/alertas", headers=admin).json() == []
    assert client.post("/alertas/evaluar", headers=admin).json() == {"creadas": 0, "cerradas": 0}  # con los límites por defecto (3 h para visitantes) dos horas todavía no son una alerta

    atrasar(db, "C-01", 300)
    alertas.evaluar(db, REGLAS)
    (a,) = client.get("/alertas", headers=admin).json()
    assert a["espacio"] == "C-01" and a["zona"] == "Fila 3" and a["activa"] and a["atendida"] is None and a["duracion_s"] >= 300 * 60

    atendida = client.post(f"/alertas/{a['id']}/atender", headers=admin).json()
    assert atendida["atendida"] is not None and atendida["atendidaPor"] == "Administrador" and atendida["activa"]
    assert client.post("/alertas/9999/atender", headers=admin).status_code == 404

    reportar(client, "CAM-02", [{"numero": "C-01", "ocupado": False}])
    alertas.evaluar(db, REGLAS)
    assert client.get("/alertas", headers=admin).json() == []
    (resuelta,) = client.get("/alertas?estado=todas", headers=admin).json()
    assert resuelta["activa"] is False and resuelta["resuelta"] is not None and resuelta["duracion_s"] is None

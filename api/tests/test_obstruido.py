"""Tercer estado (obstruido) y tiempo que lleva cada cajón en su estado."""
from datetime import timedelta

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

from app.db import Base, get_db, migrar_esquema
from app.main import app
from app.models import Espacio, Evento, TipoEspacio, TipoEvento, Zona, utcnow
from app.tiempo import formatear, segundos_desde
from helpers import KEY, login


def publicar(client, camara, **por_cajon):
    """por_cajon: A_01=("obstruido", "persona") o A_01="ocupado"."""
    espacios = []
    for clave, valor in por_cajon.items():
        estado, objeto = (valor, None) if isinstance(valor, str) else valor
        espacios.append({"numero": clave.replace("_", "-"), "ocupado": estado == "ocupado", "estado": estado, "objeto": objeto})
    r = client.post("/ingest/ocupacion", headers=KEY, json={"camara": camara, "espacios": espacios})
    assert r.status_code == 200, r.text
    return r.json()


def cajon(client, h, numero):
    return next(e for e in client.get("/espacios", headers=h).json() if e["numero"] == numero)


def eventos(client, h, numero):
    return [(e["tipo"], e["descripcion"]) for e in client.get("/eventos", headers=h).json() if numero in e["descripcion"]]


def test_un_objeto_en_un_cajon_vacio_lo_deja_obstruido_con_su_evento(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    publicar(client, "CAM-01", A_01="libre")  # estado inicial
    assert publicar(client, "CAM-01", A_01=("obstruido", "maleta"))["actualizados"] == 1
    c = cajon(client, admin, "A-01")
    assert c["estado"] == "obstruido" and c["objeto"] == "maleta" and c["desde_observado"] is True
    assert ("obstruccion", "Obstrucción en A-01: maleta") in eventos(client, admin, "A-01")
    assert not [t for t, _ in eventos(client, admin, "A-01") if t in ("entrada", "salida")]  # no es un vehículo


def test_al_retirar_el_objeto_el_cajon_vuelve_a_libre(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    publicar(client, "CAM-01", A_01="libre")
    publicar(client, "CAM-01", A_01=("obstruido", "persona"))
    publicar(client, "CAM-01", A_01="libre")
    c = cajon(client, admin, "A-01")
    assert c["estado"] == "libre" and c["objeto"] is None
    tipos = [t for t, _ in eventos(client, admin, "A-01")]
    assert "obstruccion_retirada" in tipos and tipos.count("obstruccion") == 1


def test_un_auto_que_llega_donde_habia_un_objeto_es_una_entrada(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    publicar(client, "CAM-01", A_01=("obstruido", "bicicleta"))  # estado inicial: obstruido
    publicar(client, "CAM-01", A_01="ocupado")
    tipos = [t for t, _ in eventos(client, admin, "A-01")]
    assert "entrada" in tipos and "obstruccion_retirada" in tipos and cajon(client, admin, "A-01")["objeto"] is None


def test_un_cajon_obstruido_no_cuenta_como_libre(client):
    demo = login(client, "demo@iest.edu.mx", "demo-pass-123")
    publicar(client, "CAM-01", A_01="libre", A_02="libre")
    publicar(client, "CAM-01", A_02=("obstruido", "persona"))
    e = client.get("/sistema/estado", headers=demo).json()["espacios"]
    assert e["libre"] == 1 and e["obstruido"] == 1 and e["ocupado"] == 0 and e["monitoreados"] == 2


def test_compatibilidad_con_clientes_que_solo_envian_ocupado(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-03", "ocupado": False}]})
    client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-03", "ocupado": True}]})
    assert cajon(client, admin, "A-03")["estado"] == "ocupado"


def test_el_estado_manda_sobre_el_campo_ocupado(client):
    r = client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-03", "ocupado": True, "estado": "obstruido"}]})
    assert r.status_code == 200
    assert client.post("/ingest/ocupacion", headers=KEY, json={"camara": "CAM-01", "espacios": [{"numero": "A-03", "ocupado": False, "estado": "roto"}]}).status_code == 422


# --- tiempo en el estado -----------------------------------------------------------------------------------
def test_formato_de_duraciones():
    assert [formatear(s) for s in (40, 90, 3700, 7200, 90000)] == ["40 s", "1 min", "1 h 1 min", "2 h", "1 d 1 h"]
    assert segundos_desde(None) is None


def test_un_cajon_sin_monitoreo_no_tiene_duracion(client):
    demo = login(client, "demo@iest.edu.mx", "demo-pass-123")
    c = cajon(client, demo, "H-01")
    assert c["duracion_s"] is None and c["desde"] is None


def test_la_primera_observacion_da_una_duracion_minima(client):
    demo = login(client, "demo@iest.edu.mx", "demo-pass-123")
    publicar(client, "CAM-01", A_01="ocupado")
    c = cajon(client, demo, "A-01")
    assert c["desde_observado"] is False and 0 <= c["duracion_s"] < 5  # empezó a verse ahora: no se sabe cuánto llevaba antes


def _retroceder(client, numero, segundos):
    """Hace que el cajón lleve `segundos` más en su estado (sin esperar de verdad)."""
    db = next(app.dependency_overrides[get_db]())
    esp = db.scalar(select(Espacio).where(Espacio.numero == numero))
    esp.estado_desde = utcnow() - timedelta(seconds=segundos)
    db.commit()


def test_la_duracion_crece_y_se_reinicia_con_un_cambio_observado(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    publicar(client, "CAM-01", A_01="libre")
    publicar(client, "CAM-01", A_01="ocupado")  # el auto llega: la cámara vio el cambio
    c = cajon(client, admin, "A-01")
    assert c["desde_observado"] is True and c["duracion_s"] < 5
    _retroceder(client, "A-01", 3 * 3600 + 120)  # lleva 3 h 2 min estacionado
    assert 3 * 3600 + 119 <= cajon(client, admin, "A-01")["duracion_s"] <= 3 * 3600 + 130
    publicar(client, "CAM-01", A_01="libre")  # se va
    salida = next(d for t, d in eventos(client, admin, "A-01") if t == "salida")
    assert "estuvo 3 h 2 min" in salida
    assert cajon(client, admin, "A-01")["duracion_s"] < 5  # ahora cuenta cuánto lleva libre


def test_si_no_se_vio_la_llegada_la_estancia_es_un_minimo(client):
    admin = login(client, "admin@iest.edu.mx", "admin-pass-123")
    publicar(client, "CAM-01", A_01="ocupado")  # ya estaba ahí cuando la cámara empezó a verlo
    _retroceder(client, "A-01", 600)
    publicar(client, "CAM-01", A_01="libre")
    assert "al menos 10 min" in next(d for t, d in eventos(client, admin, "A-01") if t == "salida")


def test_ranking_de_los_que_llevan_mas_tiempo(client):
    demo = login(client, "demo@iest.edu.mx", "demo-pass-123")
    publicar(client, "CAM-01", A_01="ocupado", A_02="ocupado", A_03="libre")
    _retroceder(client, "A-02", 7200)
    _retroceder(client, "A-01", 600)
    lista = client.get("/sistema/estancias", headers=demo).json()
    assert [x["numero"] for x in lista] == ["A-02", "A-01"] and lista[0]["duracion_s"] >= 7200
    assert lista[0]["desde"].endswith("Z") or lista[0]["desde"].endswith("+00:00")  # con zona horaria: la app lo convierte bien
    assert client.get("/sistema/estancias?estado=libre", headers=demo).json()[0]["numero"] == "A-03"


# --- migración de una base creada antes de este cambio ---------------------------------------------------------
def test_migracion_de_una_base_antigua_conserva_los_datos(tmp_path):
    ruta = tmp_path / "vieja.db"
    eng = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(eng)
    with eng.begin() as con:  # se deja la base como estaba antes: sin columnas nuevas y con el CHECK anterior
        con.exec_driver_sql("DROP TABLE espacios")
        con.exec_driver_sql("DROP TABLE eventos")
        con.exec_driver_sql("""CREATE TABLE espacios (id INTEGER PRIMARY KEY, numero VARCHAR(20) NOT NULL, zona_id INTEGER NOT NULL, camara_id INTEGER,
            tipo VARCHAR(30) NOT NULL, estado VARCHAR(30) NOT NULL, monitoreado BOOLEAN NOT NULL DEFAULT 0, roi JSON, usuario_asignado_id INTEGER,
            colgante_actual_id INTEGER, actualizado_en DATETIME NOT NULL, UNIQUE (zona_id, numero),
            CONSTRAINT estadoespacio CHECK (estado IN ('libre', 'ocupado', 'reservado', 'fuera_de_servicio')))""")
        con.exec_driver_sql("""CREATE TABLE eventos (id INTEGER PRIMARY KEY, tipo VARCHAR(30) NOT NULL, descripcion TEXT NOT NULL, espacio_id INTEGER, camara_id INTEGER,
            colgante_id INTEGER, confianza FLOAT, creado_en DATETIME NOT NULL,
            CONSTRAINT tipoevento CHECK (tipo IN ('entrada', 'salida', 'cambio_ocupacion', 'error_deteccion', 'camara_desconectada', 'camara_restablecida')))""")
        con.exec_driver_sql("INSERT INTO espacios (id, numero, zona_id, tipo, estado, monitoreado, actualizado_en) VALUES (1, 'A-01', 1, 'general', 'ocupado', 1, '2026-10-01 10:00:00')")
        con.exec_driver_sql("INSERT INTO eventos (id, tipo, descripcion, espacio_id, creado_en) VALUES (1, 'entrada', 'Entrada en A-01', 1, '2026-10-01 10:00:00')")
    migrar_esquema(eng)
    assert {"estado_desde", "inicio_observado", "objeto"} <= {c["name"] for c in inspect(eng).get_columns("espacios")}
    with eng.begin() as con:
        assert con.execute(text("SELECT numero, estado FROM espacios")).all() == [("A-01", "ocupado")]
        assert con.execute(text("SELECT descripcion FROM eventos")).all() == [("Entrada en A-01",)]
        con.exec_driver_sql("UPDATE espacios SET estado='obstruido' WHERE id=1")  # el CHECK nuevo ya lo acepta
        con.exec_driver_sql("INSERT INTO eventos (tipo, descripcion, creado_en) VALUES ('obstruccion', 'x', '2026-10-01 10:00:00')")
    migrar_esquema(eng)  # volver a correrla no rompe nada
    with Session(eng) as s:
        assert s.scalar(select(Espacio.numero)) == "A-01"


# --- distribución real: los cajones que no existen se quitan ------------------------------------------------
def test_ajustar_cajones_quita_los_que_la_distribucion_real_no_tiene(client):
    from app import seed

    db = next(app.dependency_overrides[get_db]())
    zona = db.scalar(select(Zona).where(Zona.nombre == "B"))
    db.add_all([Espacio(numero="B-40", zona_id=zona.id, tipo=TipoEspacio.general), Espacio(numero="B-41", zona_id=zona.id, tipo=TipoEspacio.general)])  # una base de cuando las islas eran de 40
    db.flush()
    sobrante = db.scalar(select(Espacio).where(Espacio.numero == "B-41"))
    db.add(Evento(tipo=TipoEvento.entrada, descripcion="Entrada en B-41", espacio_id=sobrante.id))
    db.commit()
    assert seed.ajustar_cajones(db) == 2
    assert seed.ajustar_cajones(db) == 0  # idempotente
    assert db.scalar(select(func.count()).select_from(Espacio).where(Espacio.zona_id == zona.id)) == 36
    assert db.scalar(select(Evento.espacio_id).where(Evento.descripcion == "Entrada en B-41")) is None  # el historial se conserva

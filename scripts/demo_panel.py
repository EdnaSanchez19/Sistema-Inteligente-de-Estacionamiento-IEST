"""Enseña el panel con datos SIMULADOS, sin cámaras ni GPU (para presentar o para trabajar en la interfaz).

    python scripts/demo_panel.py                 # http://localhost:8010/panel
    python scripts/demo_panel.py --ocupacion 0.9 # casi lleno

Usa una base de datos aparte (api/demo.db): no toca la del sistema real ni necesita que esté apagado.
El usuario y la clave quedan en credenciales_demo.txt (archivo local, no se sube a git).

Simula lo que enviaría el servidor de visión: la ocupación de los cajones que de verdad cubren las cámaras
(camaras/camaras.json), coches que entran y salen, las estadísticas del modelo y dos semanas de historial
para los reportes. Todo lo que se ve es inventado: NO sirve para medir nada del sistema real.
"""
import argparse
import json
import math
import os
import random
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
BASE = API_DIR / "demo.db"
CREDENCIALES = ROOT / "credenciales_demo.txt"
MODELO = {"CAM-01": ("Isla 1 y 2", 241), "CAM-02": ("Islas 3 a 7", 316)}  # nombre y latencia típica medida (ms)


def perfil(local: datetime) -> float:
    """Fracción de cajones ocupados a una hora local: mañana llena, tarde media, noche vacía, fin de semana casi vacío."""
    h = local.hour + local.minute / 60
    campana = lambda centro, ancho: math.exp(-((h - centro) / ancho) ** 2)  # noqa: E731
    dia = 0.04 + 0.86 * campana(10.5, 2.6) + 0.45 * campana(17.5, 2.2)
    return min(0.97, dia * (0.18 if local.weekday() >= 5 else 1.0))


def preparar_entorno() -> dict:
    nueva = not BASE.exists()
    env = {**os.environ, "DATABASE_URL": "sqlite:///./demo.db", "JWT_SECRET": secrets.token_urlsafe(32), "INGEST_API_KEY": secrets.token_urlsafe(24)}
    if nueva:
        admin, demo = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(9), os.environ.get("SEED_DEMO_PASSWORD") or secrets.token_urlsafe(9)
        env.update(SEED_ADMIN_PASSWORD=admin, SEED_DEMO_PASSWORD=demo)
        CREDENCIALES.write_text(f"Panel de DEMOSTRACIÓN (datos simulados, archivo local)\n\nAdministrador: admin@iest.edu.mx / {admin}\nUsuario:       demo@iest.edu.mx / {demo}\n", encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "app.seed", "--demo", "--muestra", "60"], cwd=API_DIR, env=env, capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            raise SystemExit("No se pudo crear la base de demostración: " + r.stderr[-800:])
    return env


def sembrar_historial(dias: int, utc_offset_h: int) -> None:
    """Dos semanas de muestras de ocupación por zona, con el mismo perfil que la simulación en vivo."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.db import engine
    from app.models import Espacio, Evento, MuestraOcupacion, TipoEvento

    rng = random.Random(7)
    cubiertos = {n for ids in cajones_por_camara().values() for n in ids}
    with Session(engine) as db:
        if db.scalar(select(func.count()).select_from(MuestraOcupacion)):
            return
        por_zona: dict[int, int] = {}
        for esp in db.scalars(select(Espacio)):
            if esp.numero in cubiertos:
                por_zona[esp.zona_id] = por_zona.get(esp.zona_id, 0) + 1
        ahora = datetime.now(timezone.utc)
        t = ahora - timedelta(days=dias)
        filas, eventos, antes = [], [], None
        while t < ahora - timedelta(minutes=5):
            base = perfil((t + timedelta(hours=utc_offset_h)).replace(tzinfo=None))
            total = 0
            for zona_id, n in por_zona.items():
                ocupados = max(0, min(n, round(n * min(0.99, max(0.0, base + rng.gauss(0, 0.05))))))
                total += ocupados
                filas.append({"tomada_en": t, "zona_id": zona_id, "libres": n - ocupados, "ocupados": ocupados, "obstruidos": 0, "monitoreados": n})
            if antes is not None and t > ahora - timedelta(days=7):  # entradas y salidas de la última semana, para el resumen
                cambio = total - antes
                tipo = TipoEvento.entrada if cambio > 0 else TipoEvento.salida
                eventos += [{"tipo": tipo, "descripcion": f"{'Entrada' if cambio > 0 else 'Salida'} (historial simulado)", "creado_en": t} for _ in range(min(abs(cambio), 40))]
            antes = total
            t += timedelta(minutes=10)
        db.execute(MuestraOcupacion.__table__.insert(), filas)
        if eventos:
            db.execute(Evento.__table__.insert(), [{**e, "tipo": e["tipo"].value} for e in eventos])
        db.commit()


def cajones_por_camara() -> dict[str, list[str]]:
    cfg = json.loads((ROOT / "camaras" / "camaras.json").read_text(encoding="utf-8"))
    return {c["id"]: [s["id"] for s in c.get("spaces", [])] for c in cfg["cameras"] if c.get("spaces")}


def envejecer(rng: random.Random) -> None:
    """Reparte tiempos de estancia creíbles y deja algunos casos que disparan alertas."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app import alertas
    from app.db import engine
    from app.models import Espacio, EstadoEspacio

    ahora = datetime.now(timezone.utc)
    with Session(engine) as db:
        for esp in db.scalars(select(Espacio).where(Espacio.monitoreado.is_(True))):
            minutos = min(600, rng.expovariate(1 / 95)) if esp.estado == EstadoEspacio.ocupado else rng.uniform(1, 90)
            esp.estado_desde, esp.inicio_observado = ahora - timedelta(minutes=minutos), rng.random() < 0.8
        for numero, minutos in (("C-01", 265), ("F-02", 205), ("E-14", 790)):  # dos visitantes y un coche de más de 12 h
            esp = db.scalar(select(Espacio).where(Espacio.numero == numero))
            if esp is not None and esp.estado == EstadoEspacio.ocupado:
                esp.estado_desde, esp.inicio_observado = ahora - timedelta(minutes=minutos), True
        obstruido = db.scalar(select(Espacio).where(Espacio.numero == "D-07"))
        if obstruido is not None:
            obstruido.estado_desde = ahora - timedelta(minutes=26)
        db.commit()
        alertas.evaluar(db)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--puerto", type=int, default=8010)
    ap.add_argument("--ocupacion", type=float, default=None, help="fracción ocupada fija (0 a 1); por omisión sigue la hora del día")
    ap.add_argument("--dias", type=int, default=14, help="días de historial simulado para los reportes")
    args = ap.parse_args()

    env = preparar_entorno()
    os.environ.update({k: env[k] for k in ("DATABASE_URL", "JWT_SECRET", "INGEST_API_KEY")})
    os.chdir(API_DIR)
    sys.path.insert(0, str(API_DIR))
    import httpx

    from app.config import get_settings
    from app.db import Base, engine, migrar_esquema

    Base.metadata.create_all(engine)
    migrar_esquema()
    offset = get_settings().utc_offset_h
    sembrar_historial(args.dias, offset)

    api = f"http://127.0.0.1:{args.puerto}"
    servidor = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.puerto), "--log-level", "warning"], cwd=API_DIR, env=env)
    cliente = httpx.Client(base_url=api, headers={"X-API-Key": env["INGEST_API_KEY"]}, timeout=10)
    try:
        for _ in range(60):
            try:
                if cliente.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            raise SystemExit("La API de demostración no arrancó.")

        rng = random.Random()
        camaras = cajones_por_camara()
        objetivo = lambda: args.ocupacion if args.ocupacion is not None else max(0.35, perfil(datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=offset)))  # noqa: E731  (de noche se deja algo que ver)
        ocupado = {n: rng.random() < objetivo() for ids in camaras.values() for n in ids}
        ocupado.update({"C-01": True, "F-02": True, "E-14": True, "D-07": False})

        def enviar(calentamiento: bool = False) -> None:
            for cam, ids in camaras.items():
                espacios = [{"numero": n, "ocupado": ocupado[n], "confianza": round(rng.uniform(0.71, 0.97), 2), **({"estado": "obstruido", "objeto": "cono"} if n == "D-07" else {})} for n in ids]
                cliente.post("/ingest/ocupacion", json={"camara": cam, "espacios": espacios, "calentamiento": calentamiento}).raise_for_status()
                oc = sum(ocupado[n] for n in ids)
                nombre, latencia = MODELO.get(cam, (cam, 280))
                cliente.post("/ingest/modelo", json={"camara": cam, "modelo": "YOLOv8n + YOLOv8s", "dispositivo": "cuda:0", "imgsz": 960, "fps_video": 15, "fps_deteccion": round(1000 / latencia, 1), "latencia_ms": latencia + rng.uniform(-18, 22),
                                                     "vehiculos": oc + rng.randint(0, 3), "libres": len(ids) - oc, "ocupados": oc, "espacios": len(ids), "resolucion": "1920x1080", "umbral_confianza": 0.25, "ids": ids,
                                                     "espera_gpu_ms": rng.uniform(5, 60), "errores": 0, "luz": "normal"}).raise_for_status()
                quietos = [{"id": i, "x": rng.random(), "y": rng.random(), "estado": "quieto", "quieto_s": rng.uniform(60, 9000), "visto_s": 9000, "cajon": n} for i, n in enumerate(ids) if ocupado[n]][:40]
                moviles = [{"id": 900 + i, "x": rng.random(), "y": rng.random(), "estado": "en_movimiento", "quieto_s": 0, "visto_s": rng.uniform(3, 40), "cajon": None} for i in range(rng.randint(0, 3))]
                cliente.post("/ingest/vehiculos", json={"camara": cam, "vehiculos": quietos + moviles, "resumen": {"total": len(quietos) + len(moviles), "quietos": len(quietos), "en_movimiento": len(moviles), "fuera_de_cajon": 0}})

        enviar(calentamiento=True)
        envejecer(rng)
        print(f"\nPanel de demostración: http://localhost:{args.puerto}/panel   (usuario y clave en {CREDENCIALES.name})\nDatos simulados. Ctrl+C para detenerlo.\n")
        fijos = {"C-01", "F-02", "E-14", "D-07"}
        while servidor.poll() is None:
            time.sleep(4)
            meta, nombres = objetivo(), [n for n in ocupado if n not in fijos]
            for n in rng.sample(nombres, k=rng.randint(0, 2)):  # un par de coches entran o salen, tendiendo a la ocupación objetivo
                actual = sum(ocupado.values()) / len(ocupado)
                ocupado[n] = rng.random() < (0.5 + (meta - actual) * 4)
            enviar()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.terminate()


if __name__ == "__main__":
    main()

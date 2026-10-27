"""Levanta la demostración completa con un solo comando.

    python scripts/iniciar_demo.py            # abre http://localhost:8000/panel
    python scripts/iniciar_demo.py --sin-navegador

Qué arranca (y se detiene todo junto con Ctrl+C):
  1. La API (FastAPI) con una base SQLite local.
  2. El servidor de visión en modo demostración: procesa un video como si fuera una cámara fija, detecta vehículos
     con YOLO, publica la ocupación de la isla A en la API y emite el video anotado.
  3. Un simulador que mueve vehículos en las islas B a H para que haya eventos en vivo.

La primera vez prepara lo que falta: .env con claves aleatorias, base de datos con usuarios de demostración
(se guardan en credenciales_demo.txt, que no se sube a git), el video estabilizado y el modelo YOLO (~6 MB).
"""
import argparse
import os
import re
import secrets
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def asegurar_env() -> None:
    destino = ROOT / ".env"
    if destino.exists():
        return
    texto = (ROOT / ".env.example").read_text(encoding="utf-8").replace("\r\n", "\n")
    for clave, valor in {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(18),
        "DATABASE_URL": "sqlite:///./dev.db",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "INGEST_API_KEY": secrets.token_urlsafe(32),
    }.items():
        texto = re.sub(rf"^{clave}=.*$", f"{clave}={valor}", texto, flags=re.M)
    destino.write_text(texto, encoding="utf-8", newline="\n")
    print("Creado .env con claves aleatorias")


def asegurar_base_de_datos() -> None:
    if (ROOT / "api" / "dev.db").exists() and (ROOT / "credenciales_demo.txt").exists():
        return
    admin, demo = secrets.token_urlsafe(10), secrets.token_urlsafe(10)
    (ROOT / "api" / "dev.db").unlink(missing_ok=True)
    r = subprocess.run([PY, "-m", "app.seed", "--demo"], cwd=ROOT / "api", env={**ENV, "SEED_ADMIN_PASSWORD": admin, "SEED_DEMO_PASSWORD": demo}, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit("No se pudo crear la base de datos:\n" + r.stderr[-800:])
    (ROOT / "credenciales_demo.txt").write_text(
        f"Usuarios de demostración (archivo local, no se sube a git)\n\nAdministrador: admin@iest.edu.mx / {admin}\nUsuario demo:  demo@iest.edu.mx / {demo}\n", encoding="utf-8")
    print("Base de datos creada. Claves de acceso en credenciales_demo.txt")


def asegurar_video() -> None:
    if (ROOT / "demo" / "camara1_estatica.mp4").exists():
        return
    origen = ROOT / "evidencias" / "03_video_ia" / "video_original.mp4"
    if not origen.exists():
        raise SystemExit(f"Falta el video de origen: {origen}")
    print("Preparando el video de la cámara de demostración...")
    subprocess.run([PY, str(ROOT / "scripts" / "preparar_demo.py"), "--video", str(origen)], check=True, env=ENV)


def asegurar_modelo() -> None:
    modelo = ROOT / "vision" / "models" / "yolov8n.pt"
    if modelo.exists():
        return
    print("Descargando el modelo yolov8n.pt (~6 MB, de los repositorios de Ultralytics)...")
    modelo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([PY, "-c", f"from ultralytics.utils.downloads import attempt_download_asset as d; d(r'{modelo}')"], check=True, env=ENV)


def esperar(url: str, segundos: int = 60) -> bool:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            if requests.get(url, timeout=1.5).ok:
                return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puerto-api", type=int, default=8000)
    ap.add_argument("--puerto-video", type=int, default=8100)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()

    asegurar_env()
    asegurar_base_de_datos()
    asegurar_video()
    asegurar_modelo()

    api = f"http://127.0.0.1:{args.puerto_api}"
    procesos: list[subprocess.Popen] = []
    try:
        procesos.append(subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(args.puerto_api), "--log-level", "warning"], cwd=ROOT / "api", env=ENV))
        if not esperar(f"{api}/health"):
            raise SystemExit("La API no arrancó (¿el puerto está ocupado?)")
        procesos.append(subprocess.Popen([PY, "-m", "parking_vision.demo_server", "--config", "../demo/cameras_demo.json", "--puerto", str(args.puerto_video)], cwd=ROOT / "vision", env={**ENV, "API_URL": api}))
        procesos.append(subprocess.Popen([PY, str(ROOT / "scripts" / "simulate_cameras.py"), "--api", api, "--interval", "3", "--zonas", "B,C,D,E,F,G,H"], env=ENV, stdout=subprocess.DEVNULL))
        esperar(f"http://127.0.0.1:{args.puerto_video}/estado", 120)
        url = f"{api.replace('127.0.0.1', 'localhost')}/panel"
        print(f"\nDemostración lista: {url}\nUsuarios y claves: credenciales_demo.txt\nCtrl+C para detener todo.\n")
        if not args.sin_navegador:
            webbrowser.open(url)
        while all(p.poll() is None for p in procesos):
            time.sleep(1)
        print("Un proceso terminó; se detiene la demostración.")
    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        for p in procesos:
            if p.poll() is None:
                p.terminate()
        for p in procesos:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()

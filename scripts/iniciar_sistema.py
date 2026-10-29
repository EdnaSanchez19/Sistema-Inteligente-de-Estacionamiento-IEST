"""Levanta el sistema con un solo comando, usando videos como cámaras.

    python scripts/iniciar_sistema.py                 # abre http://localhost:8000/panel
    python scripts/iniciar_sistema.py --sin-navegador
    python scripts/iniciar_sistema.py --oculto --host 127.0.0.1   # sin ventanas, con registro en logs/ (lo usa scripts/servicio.ps1)
    python scripts/iniciar_sistema.py --con-simulacion   # además llena el resto de los cajones con datos inventados

Qué arranca (y se detiene todo junto con Ctrl+C):
  1. La API (FastAPI) con una base SQLite local.
  2. El servidor de visión: procesa cada video como si fuera una cámara fija, detecta vehículos con YOLO, decide qué
     cajones están libres u ocupados, lo publica en la API y emite el video anotado. CAM-01 (isla A) usa un video
     generado con IA; CAM-02 (isla B) usa una cámara de seguridad real si copias su video a demo/camara2_cctv.mp4.

Solo hay datos reales de lo que una cámara observa: los cajones que ninguna cámara cubre aparecen como "sin
monitoreo", no como libres. `--con-simulacion` es solo para pruebas de carga o para ver el panel lleno: arranca un
simulador con datos INVENTADOS (y los usuarios y colgantes de muestra que necesita), no mezclar con operación real.

La primera vez prepara lo que falta: .env con claves aleatorias, la base de datos con el usuario administrador
(su clave queda en credenciales.txt, que no se sube a git), el video estabilizado y el modelo YOLO (~6 MB).
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
CREDENCIALES = ROOT / "credenciales.txt"
LOGS = ROOT / "logs"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # solo existe en Windows


def lanzar(cmd, oculto: bool, registro=None, silencio: bool = False, **kw) -> subprocess.Popen:
    """Arranca un proceso hijo; en modo oculto sin ventana de consola y con su salida en logs/."""
    if oculto:
        kw.update(creationflags=SIN_VENTANA, stdout=registro, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    elif silencio:
        kw.update(stdout=subprocess.DEVNULL)
    return subprocess.Popen(cmd, **kw)


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


def asegurar_base_de_datos(con_simulacion: bool) -> None:
    base = ROOT / "api" / "dev.db"
    cajones: list[str] = []  # los cajones son los del estacionamiento real (api/app/seed.py), no los que dibujan los videos de demostración
    if base.exists() and CREDENCIALES.exists():
        # idempotente: solo agrega lo que falte (colgantes de muestra), quita los cajones que la distribución real no tiene y pone al día el esquema
        r = subprocess.run([PY, "-m", "app.seed", *cajones] + (["--muestra", "150"] if con_simulacion else []), cwd=ROOT / "api", env=ENV, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit("No se pudo actualizar la base de datos: " + r.stderr[-800:])
        return
    admin = secrets.token_urlsafe(10)
    base.unlink(missing_ok=True)
    cmd = [PY, "-m", "app.seed", *cajones] + (["--muestra", "150"] if con_simulacion else [])
    r = subprocess.run(cmd, cwd=ROOT / "api", env={**ENV, "SEED_ADMIN_PASSWORD": admin}, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit("No se pudo crear la base de datos:\n" + r.stderr[-800:])
    CREDENCIALES.write_text(f"Acceso al panel (archivo local, no se sube a git)\n\nAdministrador: admin@iest.edu.mx / {admin}\n", encoding="utf-8")
    print("Base de datos creada. Clave del administrador en credenciales.txt")


def asegurar_video() -> None:
    if (ROOT / "demo" / "camara1_estatica.mp4").exists():
        return
    origen = ROOT / "evidencias" / "03_video_ia" / "video_original.mp4"
    if not origen.exists():
        raise SystemExit(f"Falta el video de origen: {origen}")
    print("Preparando el video de la cámara CAM-01...")
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
    ap.add_argument("--host", default="0.0.0.0", help="dirección de la API; 127.0.0.1 = solo este equipo (lo recomendado si queda corriendo siempre)")
    ap.add_argument("--oculto", action="store_true", help="sin ventanas: la salida va a logs/sistema.log y el PID a logs/sistema.pid")
    ap.add_argument("--con-simulacion", action="store_true", help="agrega un simulador con datos inventados para el resto de los cajones")
    args = ap.parse_args()

    asegurar_env()
    asegurar_base_de_datos(args.con_simulacion)
    asegurar_video()
    asegurar_modelo()
    if not (ROOT / "demo" / "camara2_cctv.mp4").exists():
        print("Aviso: sin demo/camara2_cctv.mp4 no se activa CAM-02 (isla B); esa isla quedará sin monitoreo.")

    api = f"http://127.0.0.1:{args.puerto_api}"
    procesos: list[subprocess.Popen] = []
    registro = None
    if args.oculto:
        LOGS.mkdir(exist_ok=True)
        if (LOGS / "sistema.log").exists() and (LOGS / "sistema.log").stat().st_size > 5_000_000:  # un solo archivo anterior, sin crecer sin límite
            (LOGS / "sistema.log").replace(LOGS / "sistema.anterior.log")
        registro = open(LOGS / "sistema.log", "a", encoding="utf-8", buffering=1)
        (LOGS / "sistema.pid").write_text(str(os.getpid()), encoding="utf-8")
        sys.stdout = sys.stderr = registro  # con pythonw no hay consola: lo que se imprima queda en el registro
        print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} arranque (API en {args.host}:{args.puerto_api}) ===", flush=True)
    try:
        procesos.append(lanzar([PY, "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.puerto_api), "--log-level", "warning"], args.oculto, registro, cwd=ROOT / "api", env=ENV))
        if not esperar(f"{api}/health"):
            raise SystemExit("La API no arrancó (¿el puerto está ocupado?)")
        procesos.append(lanzar([PY, "-m", "parking_vision.demo_server", "--config", "../demo/cameras_demo.json", "--puerto", str(args.puerto_video)], args.oculto, registro, cwd=ROOT / "vision", env={**ENV, "API_URL": api}))
        if args.con_simulacion:
            print("ATENCIÓN: --con-simulacion llena el resto de los cajones con datos inventados.")
            procesos.append(lanzar([PY, str(ROOT / "scripts" / "simulate_cameras.py"), "--api", api, "--interval", "3"], args.oculto, registro, silencio=True, env=ENV))
        esperar(f"http://127.0.0.1:{args.puerto_video}/estado", 120)
        url = f"{api.replace('127.0.0.1', 'localhost')}/panel"
        print(f"\nSistema listo: {url}\nUsuario y clave: credenciales.txt\nCtrl+C para detener todo.\n")
        if not args.sin_navegador and not args.oculto:
            webbrowser.open(url)
        while all(p.poll() is None for p in procesos):
            time.sleep(1)
        print("Un proceso terminó; se detiene el sistema.")
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
        if args.oculto:
            (LOGS / "sistema.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()

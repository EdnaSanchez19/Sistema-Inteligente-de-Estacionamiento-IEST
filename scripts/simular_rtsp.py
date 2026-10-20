"""Simula una cámara IP: publica un video en bucle por RTSP con ffmpeg + mediamtx (servidor RTSP).

    python scripts/simular_rtsp.py --video datasets/prueba_sintetica/video.mp4
    # el servidor de visión se conecta a rtsp://127.0.0.1:8554/cam1

    python scripts/simular_rtsp.py --video v.mp4 --caida-tras 20 --pausa 10   # se "cae" 10 s cada 20 s

Requisitos (no se incluyen en el repo):
  - ffmpeg en el PATH (o --ffmpeg).
  - mediamtx (https://github.com/bluenviron/mediamtx/releases, un solo ejecutable). Se busca en
    herramientas_externas/mediamtx/, en el PATH o con --mediamtx.

ffmpeg no puede ser servidor RTSP por sí solo (solo publica), por eso se usa mediamtx. La "caída" detiene la
publicación: los clientes pierden la señal y se reconectan cuando la cámara vuelve, como con una cámara real.
"""
import argparse
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIAMTX_LOCAL = ROOT / "herramientas_externas" / "mediamtx" / "mediamtx.exe"


def buscar_mediamtx() -> str | None:
    if MEDIAMTX_LOCAL.is_file():
        return str(MEDIAMTX_LOCAL)
    return shutil.which("mediamtx")


def lanzar_servidor(mediamtx: str, puerto: int) -> subprocess.Popen:
    env = {
        **os.environ,
        "MTX_RTSPADDRESS": f":{puerto}",
        "MTX_RTSPTRANSPORTS": "tcp",
        "MTX_RTMP": "no", "MTX_HLS": "no", "MTX_WEBRTC": "no", "MTX_SRT": "no", "MTX_API": "no", "MTX_METRICS": "no", "MTX_PPROF": "no",
        "MTX_LOGLEVEL": "error",
    }
    return subprocess.Popen([mediamtx], cwd=Path(mediamtx).parent, env=env)


def publicar(ffmpeg: str, video: Path, url: str) -> subprocess.Popen:
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-re", "-stream_loop", "-1", "-i", str(video),
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p", "-g", "10",
        "-f", "rtsp", "-rtsp_transport", "tcp", url,
    ]
    return subprocess.Popen(cmd)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--puerto", type=int, default=8554)
    ap.add_argument("--ruta", default="cam1")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    ap.add_argument("--mediamtx", default=buscar_mediamtx())
    ap.add_argument("--caida-tras", type=float, default=0, help="segundos tras los cuales se simula una caída (0 = nunca)")
    ap.add_argument("--pausa", type=float, default=5, help="segundos que la cámara permanece caída")
    args = ap.parse_args()
    if not args.ffmpeg:
        raise SystemExit("No se encontró ffmpeg. Instálalo o usa --ffmpeg ruta")
    if not args.mediamtx:
        raise SystemExit("No se encontró mediamtx. Descárgalo de github.com/bluenviron/mediamtx/releases o usa --mediamtx ruta")
    if not args.video.is_file():
        raise SystemExit(f"No existe el video {args.video}")

    servidor = lanzar_servidor(args.mediamtx, args.puerto)
    time.sleep(1.0)
    url = f"rtsp://127.0.0.1:{args.puerto}/{args.ruta}"
    print(f"Cámara simulada en {url}  (Ctrl+C para detener)", flush=True)
    pub = None
    try:
        while True:
            pub = publicar(args.ffmpeg, args.video, url)
            inicio = time.time()
            while pub.poll() is None:
                if args.caida_tras and time.time() - inicio >= args.caida_tras:
                    print("Simulando caída de la cámara", flush=True)
                    pub.terminate()
                    pub.wait(timeout=10)
                    time.sleep(args.pausa)
                    break
                time.sleep(0.2)
            else:
                time.sleep(1.0)  # ffmpeg terminó solo: reintentar
    except KeyboardInterrupt:
        pass
    finally:
        for p in (pub, servidor):
            if p and p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()

"""Degrada un video para simular condiciones adversas (tarea 4.4): noche, lluvia, niebla, sol de frente, ruido.

    python -m parking_vision.tools.condiciones --video dia.mp4 --condicion noche --salida noche.mp4
    python -m parking_vision.tools.condiciones --video dia.mp4 --todas --carpeta ../salida/condiciones

Son aproximaciones por filtros, no física real: sirven para ver qué tan sensible es el detector a la luz y la
nitidez y comparar contra el video original, pero no sustituyen grabar de noche o con lluvia en el estacionamiento.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def noche(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    f = (frame.astype(np.float32) / 255.0) ** 2.4 * 0.75  # oscurece las zonas medias y claras
    f *= np.array([1.15, 0.95, 0.80], np.float32)  # tinte azulado (BGR)
    f += rng.normal(0, 0.035, f.shape).astype(np.float32)  # ruido del sensor con poca luz
    return np.clip(f * 255, 0, 255).astype(np.uint8)


def lluvia(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = frame.shape[:2]
    base = cv2.GaussianBlur(frame, (3, 3), 0).astype(np.float32) * 0.82
    capa = np.zeros((h, w), np.uint8)
    for _ in range(int(h * w / 2500)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        largo = int(rng.integers(10, 28))
        cv2.line(capa, (x, y), (x - largo // 4, y + largo), int(rng.integers(120, 230)), 1)
    capa = cv2.GaussianBlur(capa, (3, 3), 0).astype(np.float32)[..., None]
    return np.clip(base + capa * 0.45, 0, 255).astype(np.uint8)


def niebla(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    blur = cv2.GaussianBlur(frame, (0, 0), 2.2).astype(np.float32)
    velo = np.full_like(blur, 205.0)
    return np.clip(blur * 0.55 + velo * 0.45, 0, 255).astype(np.uint8)


def sol_de_frente(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = frame.shape[:2]
    f = frame.astype(np.float32) * 1.45 + 25  # sobreexposición
    ys, xs = np.mgrid[0:h, 0:w]
    resplandor = np.exp(-(((xs - w * 0.8) ** 2) + ((ys - h * 0.1) ** 2)) / (2 * (min(h, w) * 0.45) ** 2))
    f += resplandor[..., None] * 140
    return np.clip(f, 0, 255).astype(np.uint8)


def ruido(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    f = frame.astype(np.float32) + rng.normal(0, 14, frame.shape)
    f = np.clip(f, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 22])  # compresión agresiva
    return cv2.imdecode(buf, cv2.IMREAD_COLOR) if ok else f


CONDICIONES = {"noche": noche, "lluvia": lluvia, "niebla": niebla, "sol": sol_de_frente, "ruido": ruido}


def aplicar(video: Path, condicion: str, salida: Path, semilla: int = 0) -> int:
    fn = CONDICIONES[condicion]
    rng = np.random.default_rng(semilla)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    salida.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(salida), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        out.write(fn(frame, rng))
        n += 1
    cap.release()
    out.release()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--condicion", choices=sorted(CONDICIONES))
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--todas", action="store_true", help="genera una versión por cada condición")
    ap.add_argument("--carpeta", type=Path, default=Path("salida/condiciones"))
    args = ap.parse_args()
    if args.todas:
        for c in CONDICIONES:
            dest = args.carpeta / f"{args.video.stem}_{c}.mp4"
            print(f"{c}: {aplicar(args.video, c, dest)} fotogramas -> {dest}")
    elif args.condicion and args.salida:
        print(f"{aplicar(args.video, args.condicion, args.salida)} fotogramas -> {args.salida}")
    else:
        ap.error("usa --todas, o --condicion y --salida")


if __name__ == "__main__":
    main()

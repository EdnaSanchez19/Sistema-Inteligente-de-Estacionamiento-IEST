"""Mide, sin etiquetas, cuánto degradan las condiciones adversas la detección de vehículos.

    python -m parking_vision.tools.comparar_condiciones --video ../datasets/estacionamiento/video.mp4 --cada 1

Para cada fotograma se detectan los vehículos en la imagen original (línea base) y en cada versión degradada
(noche, lluvia, niebla, sol, ruido). Reporta qué fracción de los vehículos de la línea base sigue encontrando
(retención) y qué fracción de lo que detecta no corresponde a ninguno de la línea base (extra). No usa la
posición de los cajones, así que sirve aunque la cámara se mueva.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from ..detector import VehicleDetector
from ..occupancy import Detection
from .condiciones import CONDICIONES


def iou(a: Detection, b: Detection) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union if union > 0 else 0.0


def emparejar(base: list[Detection], otras: list[Detection], umbral: float = 0.5) -> tuple[int, int]:
    """(vehículos de la base encontrados, detecciones sin pareja en la base). Cada detección se usa una sola vez."""
    usadas: set[int] = set()
    hallados = 0
    for b in base:
        mejor, mejor_iou = None, umbral
        for j, o in enumerate(otras):
            if j in usadas:
                continue
            v = iou(b, o)
            if v >= mejor_iou:
                mejor, mejor_iou = j, v
        if mejor is not None:
            usadas.add(mejor)
            hallados += 1
    return hallados, len(otras) - len(usadas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--model", default="models/yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--cada", type=float, default=1.0, help="segundos entre fotogramas evaluados")
    args = ap.parse_args()

    det = VehicleDetector(args.model, imgsz=args.imgsz)
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    paso = max(1, round(args.cada * fps))
    rng = np.random.default_rng(0)
    base_total = 0
    acum = {c: [0, 0, 0] for c in CONDICIONES}  # hallados, extra, total detectado
    n = i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % paso == 0:
            base = [d for d in det.detect(frame) if d.conf >= args.conf]
            base_total += len(base)
            for nombre, fn in CONDICIONES.items():
                otras = [d for d in det.detect(fn(frame, rng)) if d.conf >= args.conf]
                hallados, extra = emparejar(base, otras)
                acum[nombre][0] += hallados
                acum[nombre][1] += extra
                acum[nombre][2] += len(otras)
            n += 1
        i += 1
    cap.release()

    print(f"{n} fotogramas, {base_total} vehículos en la línea base ({base_total / max(n, 1):.0f} por fotograma)\n")
    print(f"{'condición':<10} {'retención':>10} {'extra':>8}")
    for nombre, (hallados, extra, total) in acum.items():
        print(f"{nombre:<10} {hallados / max(base_total, 1):>10.1%} {extra / max(total, 1):>8.1%}")


if __name__ == "__main__":
    main()

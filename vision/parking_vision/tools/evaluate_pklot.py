"""Evalúa el detector contra el dataset público PKLot (imágenes + XML con cajones etiquetados).

    python -m parking_vision.tools.evaluate_pklot --root D:/datasets/PKLot/PKLotSegmented/... --limit 200

Busca pares imagen .jpg / .xml en --root (recursivo). Imprime precisión, recall, exactitud y la
matriz de confusión a nivel de cajón. Sirve para la tarea 4.1 (validar con un dataset de prueba).
"""
from __future__ import annotations

import argparse
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

from ..config import CameraConfig, Space
from ..detector import VehicleDetector
from ..occupancy import compute_occupancy


def load_pklot_xml(path: Path) -> tuple[list[Space], list[bool]]:
    spaces, truth = [], []
    for sp in ET.parse(path).getroot().iter("space"):
        pts = [(float(p.get("x")), float(p.get("y"))) for p in sp.iter("point")]
        if len(pts) < 3 or sp.get("occupied") is None:
            continue
        spaces.append(Space(sp.get("id", str(len(spaces))), np.array(pts, np.float32)))
        truth.append(sp.get("occupied") == "1")
    return spaces, truth


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=100, help="máximo de imágenes a evaluar (muestreo aleatorio)")
    ap.add_argument("--conf", type=float, default=CameraConfig.conf)
    ap.add_argument("--ratio", type=float, default=CameraConfig.occupied_ratio)
    ap.add_argument("--footprint", type=float, default=CameraConfig.footprint)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    pairs = [(x.with_suffix(".jpg"), x) for x in Path(args.root).rglob("*.xml") if x.with_suffix(".jpg").exists()]
    if not pairs:
        raise SystemExit("No se encontraron pares .jpg/.xml en --root")
    random.Random(args.seed).shuffle(pairs)
    pairs = pairs[: args.limit]

    detector = VehicleDetector(args.model)
    tp = fp = tn = fn = 0
    for img_path, xml_path in pairs:
        frame = cv2.imread(str(img_path))
        spaces, truth = load_pklot_xml(xml_path)
        if frame is None or not spaces:
            continue
        dets = [d for d in detector.detect(frame) if d.conf >= args.conf]
        for st, real in zip(compute_occupancy(spaces, dets, args.ratio, args.footprint), truth):
            tp += st.occupied and real
            fp += st.occupied and not real
            fn += (not st.occupied) and real
            tn += (not st.occupied) and (not real)

    total = tp + fp + tn + fn
    div = lambda a, b: a / b if b else 0.0  # noqa: E731
    print(f"Imágenes: {len(pairs)}  Cajones evaluados: {total}")
    print(f"Exactitud: {div(tp + tn, total):.3f}  Precisión: {div(tp, tp + fp):.3f}  Recall: {div(tp, tp + fn):.3f}")
    print("Matriz de confusión (filas=real, columnas=predicho)")
    print(f"             ocupado   libre\n  ocupado   {tp:8d} {fn:7d}\n  libre     {fp:8d} {tn:7d}")


if __name__ == "__main__":
    main()

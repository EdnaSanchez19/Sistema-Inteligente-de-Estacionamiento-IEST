"""Descubre los cajones de una cámara fija a partir de dónde se estacionan los autos en el video.

    python scripts/descubrir_cajones.py --video datasets/camara2/video.mp4 --isla B --max 40 --camara CAM-02 --salida demo/cajones_cam02.json

Procesa un fotograma por segundo con YOLO, agrupa las detecciones que se repiten en el mismo lugar (autos
estacionados, no los que pasan manejando) y cada grupo estable se vuelve un cajón (B-01, B-02, ...). Es una ayuda
para dibujar los cajones más rápido en una demostración: en producción los cajones se dibujan sobre las líneas
del estacionamiento con `parking_vision.tools.define_spaces`.

OJO: así solo aparecen cajones donde hubo un auto en algún momento; los vacíos todo el video no se descubren.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
from parking_vision.detector import VehicleDetector  # noqa: E402


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--isla", default="B")
    ap.add_argument("--camara", default="CAM-02")
    ap.add_argument("--max", type=int, default=40, help="máximo de cajones (se quedan los más estables)")
    ap.add_argument("--cada", type=float, default=1.0, help="segundos entre fotogramas analizados")
    ap.add_argument("--min-presencia", type=float, default=0.10, help="fracción mínima del video en que debe haber un auto ahí")
    ap.add_argument("--max-solape", type=float, default=0.35, help="IoU a partir del cual dos grupos se consideran el mismo cajón")
    ap.add_argument("--ignorar-y-menor", type=int, default=300, help="descarta lo que esté más arriba (lejos) de esta fila en píxeles")
    ap.add_argument("--modelo", default=str(ROOT / "vision" / "models" / "yolov8n.pt"))
    ap.add_argument("--salida", type=Path, default=ROOT / "demo" / "cajones.json")
    ap.add_argument("--imagen", type=Path, default=None, help="guarda un fotograma con los cajones encontrados")
    args = ap.parse_args()

    det = VehicleDetector(args.modelo, imgsz=1280)
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    paso = max(1, round(args.cada * fps))
    grupos: list[dict] = []  # cada grupo: caja media, cuántas veces apareció
    n = i = 0
    primero = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % paso == 0:
            primero = f if primero is None else primero
            n += 1
            for d in det.detect(f):
                if d.conf < 0.35 or d.y2 < args.ignorar_y_menor:
                    continue
                caja = (d.x1, d.y1, d.x2, d.y2)
                mejor = max(grupos, key=lambda g: iou(g["caja"], caja), default=None)
                if mejor and iou(mejor["caja"], caja) >= 0.55:
                    k = mejor["n"]
                    mejor["caja"] = tuple((m * k + c) / (k + 1) for m, c in zip(mejor["caja"], caja))
                    mejor["n"] += 1
                    mejor["conf"] += d.conf
                else:
                    grupos.append({"caja": caja, "n": 1, "conf": d.conf})
        i += 1
    cap.release()

    candidatos = sorted((g for g in grupos if g["n"] / n >= args.min_presencia), key=lambda g: -g["n"])
    estables: list[dict] = []
    for g in candidatos:  # de los más estables a los menos; un grupo que se encima con uno ya aceptado es un duplicado
        if all(iou(g["caja"], e["caja"]) < args.max_solape for e in estables):
            estables.append(g)
    estables = estables[: args.max]
    # orden de lectura: de las filas lejanas a las cercanas, y de izquierda a derecha dentro de cada fila
    estables.sort(key=lambda g: (round(g["caja"][3] / 60), g["caja"][0]))
    cajones = []
    for k, g in enumerate(estables, start=1):
        x1, y1, x2, y2 = g["caja"]
        ym = y1 + (y2 - y1) * 0.45  # mitad inferior del auto: aproxima dónde toca el suelo
        poly = [[round(x1 + 3), round(ym)], [round(x2 - 3), round(ym)], [round(x2), round(y2)], [round(x1), round(y2)]]
        cajones.append({"id": f"{args.isla}-{k:02d}", "polygon": poly, "presencia": round(g["n"] / n, 2)})
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps({"camara": args.camara, "fotogramas_analizados": n, "cajones": cajones}, indent=2), encoding="utf-8")
    print(f"{n} fotogramas analizados; {len(grupos)} posiciones vistas; {len(cajones)} cajones estables -> {args.salida}")
    for c in cajones:
        print(f"  {c['id']}  presencia {c['presencia']:.0%}")
    if args.imagen and primero is not None:
        im = primero.copy()
        for c in cajones:
            pts = np.array(c["polygon"], np.int32)
            cv2.polylines(im, [pts], True, (0, 215, 255), 2)
            cx, cy = pts.mean(axis=0).astype(int)
            cv2.putText(im, c["id"][-2:], (cx - 10, cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(args.imagen), im)


if __name__ == "__main__":
    main()

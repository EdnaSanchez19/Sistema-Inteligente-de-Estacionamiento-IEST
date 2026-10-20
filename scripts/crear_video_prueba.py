"""Genera un video de PRUEBA TÉCNICA con verdad conocida, para ejercitar las herramientas de simulación.

    python scripts/crear_video_prueba.py --imagen datasets/ejemplos/bus.jpg --salida datasets/prueba_sintetica

Toma la foto de un vehículo real (por ejemplo bus.jpg) y la desplaza sobre un fondo de asfalto: entra a un
cajón, permanece y sale; otro está ocupado al inicio y se va. Escribe:
  - video.mp4            el video (10 fps, 30 s)
  - cameras.json         cámara CAM-01 con 3 cajones dibujados para ese video
  - etiquetas.csv        verdad exacta (t_seg, espacio, ocupado) cada segundo

OJO: es un montaje sintético; sirve para comprobar que el procesamiento, las métricas y la simulación de
condiciones funcionan, NO para medir la precisión real del detector. Para eso se necesita un video real.
"""
import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

W, H, FPS, DUR = 1280, 720, 10, 30
CAJON_W, CAJON_H, Y0 = 300, 400, 250
XS = [70, 490, 910]  # tres cajones: A-01, A-02, A-03


def tramo(t: float, entra: float, llega: float, sale: float, se_va: float) -> float | None:
    """Posición normalizada (0 = fuera por arriba, 1 = dentro del cajón); None si no está en escena."""
    if t < entra or t > se_va:
        return None
    if t < llega:
        return (t - entra) / (llega - entra)
    if t <= sale:
        return 1.0
    return 1.0 - (t - sale) / (se_va - sale)


# (cajón, entra, llega, sale, se_va) en segundos
GUION = [(0, -1, 0, 12, 18), (1, 5, 9, 22, 27), (2, 14, 17, 40, 41)]


def ocupado(t: float, g) -> bool:
    p = tramo(t, *g[1:])
    return p is not None and p >= 0.9


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--imagen", required=True, type=Path)
    ap.add_argument("--salida", required=True, type=Path)
    args = ap.parse_args()

    foto = cv2.imread(str(args.imagen))
    if foto is None:
        raise SystemExit(f"No se pudo leer {args.imagen}")
    escala = (CAJON_H - 40) / foto.shape[0]
    veh = cv2.resize(foto, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    vh, vw = veh.shape[:2]

    fondo = np.full((H, W, 3), 95, np.uint8)
    rng = np.random.default_rng(0)
    fondo = np.clip(fondo + rng.normal(0, 4, fondo.shape), 0, 255).astype(np.uint8)
    for x in XS:
        cv2.rectangle(fondo, (x, Y0), (x + CAJON_W, Y0 + CAJON_H), (230, 230, 230), 3)

    args.salida.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(args.salida / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(FPS * DUR):
        t = i / FPS
        frame = fondo.copy()
        for g in GUION:
            p = tramo(t, *g[1:])
            if p is None:
                continue
            x = XS[g[0]] + (CAJON_W - vw) // 2
            y = int(-vh + p * (Y0 + 20 + vh))  # entra desde arriba de la imagen
            y0, y1 = max(y, 0), min(y + vh, H)
            if y1 > y0:
                frame[y0:y1, x : x + vw] = veh[y0 - y : y1 - y]
        out.write(frame)
    out.release()

    spaces = [{"id": f"A-{i + 1:02d}", "polygon": [[x, Y0], [x + CAJON_W, Y0], [x + CAJON_W, Y0 + CAJON_H], [x, Y0 + CAJON_H]]} for i, x in enumerate(XS)]
    (args.salida / "cameras.json").write_text(
        json.dumps({"model": "models/yolov8n.pt", "cameras": [{"id": "CAM-01", "source": str(args.salida / "video.mp4"), "interval_s": 1.0, "conf": 0.35, "occupied_ratio": 0.3, "footprint": 1.0, "confirm_occupied": 2, "confirm_free": 2, "spaces": spaces}]}, indent=2),
        encoding="utf-8",
    )
    with (args.salida / "etiquetas.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_seg", "espacio", "ocupado"])
        for t in range(DUR):
            for g in GUION:
                w.writerow([t, f"A-{g[0] + 1:02d}", int(ocupado(t, g))])
    print(f"Listo en {args.salida}: video.mp4, cameras.json, etiquetas.csv")


if __name__ == "__main__":
    main()

"""Etiqueta a mano qué cajones están ocupados en fotogramas de un video (la "verdad" para medir la precisión).

    python -m parking_vision.tools.etiquetar --config config/cameras.json --camera CAM-01 \
        --video ../datasets/estacionamiento.mp4 --cada 30 --salida ../datasets/etiquetas.csv

Se muestra un fotograma cada `--cada` segundos con los cajones numerados (verde = libre, rojo = ocupado).
Controles: clic en un cajón = alternar libre/ocupado · Enter o espacio = guardar y pasar al siguiente ·
s = saltar el fotograma sin guardarlo · q o Esc = terminar (lo guardado se conserva).
Por defecto todos empiezan "libres" para que cada etiqueta sea una decisión tuya; --prellenar usa el modelo
como punto de partida (más rápido, pero corrige con cuidado: si aceptas sus errores, la medición sale inflada).
El CSV se puede seguir ampliando: si ya existe, se agregan filas.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from ..config import Space, load_config
from ..draw import draw_result
from ..occupancy import SpaceState


def espacio_en(x: float, y: float, spaces: list[Space]) -> int | None:
    """Índice del cajón que contiene el punto (x, y), o None."""
    for i, sp in enumerate(spaces):
        if cv2.pointPolygonTest(sp.polygon.astype(np.float32), (float(x), float(y)), False) >= 0:
            return i
    return None


def escribir_filas(path: Path, t: float, spaces: list[Space], ocupados: list[bool]) -> None:
    nuevo = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["t_seg", "espacio", "ocupado"])
        for sp, occ in zip(spaces, ocupados):
            w.writerow([round(t, 2), sp.id, int(occ)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/cameras.json")
    ap.add_argument("--camera", required=True)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--cada", type=float, default=30.0, help="segundos entre fotogramas a etiquetar")
    ap.add_argument("--desde", type=float, default=0.0)
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--prellenar", action="store_true", help="usar la predicción del modelo como punto de partida")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cam = next((c for c in cfg.cameras if c.id == args.camera), None)
    if cam is None:
        raise SystemExit(f"La cámara {args.camera} no está en {args.config}")
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_s = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    detector = None
    if args.prellenar:
        from ..detector import VehicleDetector
        from ..occupancy import compute_occupancy

        detector = VehicleDetector(cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes)

    ocupados: list[bool] = []
    win = "Etiquetar (clic = alternar, Enter = guardar, s = saltar, q = salir)"

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            i = espacio_en(x, y, cam.spaces)
            if i is not None:
                ocupados[i] = not ocupados[i]

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    guardados = 0
    t = args.desde
    while t < total_s:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        if detector:
            dets = [d for d in detector.detect(frame) if d.conf >= cam.conf]
            ocupados = [s.occupied for s in compute_occupancy(cam.spaces, dets, cam.occupied_ratio, cam.footprint)]
        else:
            ocupados = [False] * len(cam.spaces)
        accion = None
        while accion is None:
            estados = [SpaceState(sp.id, o) for sp, o in zip(cam.spaces, ocupados)]
            vista = draw_result(frame, cam.spaces, estados)
            cv2.putText(vista, f"t = {t:.0f} s ({guardados} guardados)", (8, vista.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow(win, vista)
            k = cv2.waitKey(30) & 0xFF
            if k in (13, 32):
                accion = "guardar"
            elif k == ord("s"):
                accion = "saltar"
            elif k in (ord("q"), 27):
                accion = "salir"
        if accion == "salir":
            break
        if accion == "guardar":
            escribir_filas(args.salida, t, cam.spaces, ocupados)
            guardados += 1
        t += args.cada
    cap.release()
    cv2.destroyAllWindows()
    print(f"{guardados} fotogramas etiquetados en {args.salida}")


if __name__ == "__main__":
    main()

"""Dibuja las ROI de los cajones sobre un fotograma de la cámara y las guarda en el JSON.

    python -m parking_vision.tools.define_spaces --config config/cameras.json --camera CAM-01 \
        --source rtsp://... --prefix A

Controles: clic = agregar punto (4 por cajón), Enter/Espacio = cerrar cajón (si ya hay >= 3 puntos),
u = deshacer, s = guardar y salir, q/Esc = salir sin guardar.
"""
from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

from ..capture import CameraStream
from ..config import Space, load_dotenv, save_spaces


def grab_frame(source: str) -> np.ndarray:
    stream = CameraStream(source).start()
    deadline = time.time() + 15
    while time.time() < deadline:
        frame, _ = stream.latest()
        if frame is not None:
            stream.stop()
            return frame
        time.sleep(0.2)
    stream.stop()
    raise SystemExit(f"No se pudo leer un fotograma de {source!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/cameras.json")
    ap.add_argument("--camera", required=True, help="id de la cámara, p. ej. CAM-01")
    ap.add_argument("--source", required=True, help="URL RTSP, imagen o video (usa ${VAR} para credenciales)")
    ap.add_argument("--prefix", required=True, help="prefijo de los cajones, p. ej. A -> A-01, A-02...")
    ap.add_argument("--start", type=int, default=1, help="número del primer cajón")
    args = ap.parse_args()

    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    import os, re

    resolved = re.sub(r"\$\{(\w+)\}", lambda m: os.environ[m.group(1)], args.source)
    base = grab_frame(resolved)
    spaces: list[Space] = []
    current: list[tuple[int, int]] = []

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            current.append((x, y))

    win = "Define cajones"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    while True:
        view = base.copy()
        for i, sp in enumerate(spaces):
            cv2.polylines(view, [sp.polygon.astype(np.int32)], True, (60, 180, 75), 2)
            cx, cy = sp.polygon.mean(axis=0).astype(int)
            cv2.putText(view, sp.id, (cx - 18, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        for p in current:
            cv2.circle(view, p, 4, (0, 200, 255), -1)
        if len(current) > 1:
            cv2.polylines(view, [np.array(current, np.int32)], False, (0, 200, 255), 1)
        nxt = f"{args.prefix}-{args.start + len(spaces):02d}"
        cv2.putText(view, f"Siguiente: {nxt}  (Enter=cerrar, u=deshacer, s=guardar, q=salir)", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(win, view)
        key = cv2.waitKey(30) & 0xFF
        if key in (13, 32) and len(current) >= 3:
            spaces.append(Space(nxt, np.array(current, np.float32)))
            current.clear()
        elif key == ord("u"):
            if current:
                current.pop()
            elif spaces:
                spaces.pop()
        elif key == ord("s"):
            save_spaces(args.config, args.camera, args.source, spaces)
            print(f"Guardados {len(spaces)} cajones de {args.camera} en {args.config}")
            break
        elif key in (ord("q"), 27):
            print("Cancelado, no se guardó nada")
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""Prepara los videos y la configuración de la demostración del panel (carpeta demo/).

    python scripts/preparar_demo.py --video evidencias/03_video_ia/video_original.mp4

Con el video generado con IA (toma aérea que avanza) hace que parezca una cámara fija: alinea cada fotograma
con el primero (misma técnica del estabilizador), recorta los bordes negros que quedan y reproduce el tramo
estable hacia adelante y hacia atrás, de modo que el bucle no tenga saltos. Los cajones de la cámara se
dibujaron a ojo sobre el fotograma estabilizado (9 con auto y 3 sobre asfalto vacío).

Es una demostración visual: el video es generado con IA y no hay entradas ni salidas de vehículos reales.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / "vision"))
from parking_vision.estabilizar import Estabilizador  # noqa: E402

def paralelogramo(nariz, cola, semiancho):
    """Cajón alineado con el eje del auto (de la nariz a la cola), como en una toma oblicua."""
    (x1, y1), (x2, y2) = nariz, cola
    dx, dy = x2 - x1, y2 - y1
    largo = (dx * dx + dy * dy) ** 0.5
    nx, ny = -dy / largo * semiancho, dx / largo * semiancho
    return [[round(x1 + nx), round(y1 + ny)], [round(x2 + nx), round(y2 + ny)], [round(x2 - nx), round(y2 - ny)], [round(x1 - nx), round(y1 - ny)]]


# Cajones dibujados a ojo sobre el fotograma ya estabilizado y recortado (1280x720): (nariz, cola, semiancho)
AUTOS = [
    ((185, 505), (455, 600), 75), ((355, 435), (620, 500), 62), ((490, 350), (725, 405), 50),
    ((590, 305), (805, 350), 45), ((670, 265), (885, 300), 38), ((735, 235), (935, 262), 32),
    ((145, 330), (345, 385), 55), ((490, 215), (630, 260), 40), ((575, 180), (710, 220), 35),
]
CAJONES = {f"A-{i + 1:02d}": paralelogramo(*a) for i, a in enumerate(AUTOS)}
# tres cajones sobre asfalto vacío (control: deben salir libres)
VACIOS = [[[700, 520], [840, 495], [900, 580], [760, 610]], [[1000, 430], [1100, 410], [1130, 480], [1020, 510]], [[850, 630], [980, 610], [1030, 690], [900, 715]]]
CAJONES.update({f"A-{len(AUTOS) + i + 1:02d}": v for i, v in enumerate(VACIOS)})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--salida", type=Path, default=ROOT / "demo")
    ap.add_argument("--hasta", type=float, default=3.5, help="segundos del video que se usan (la toma se aleja después)")
    ap.add_argument("--recorte", type=float, default=0.10, help="fracción que se recorta por cada lado")
    args = ap.parse_args()

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    est = Estabilizador()
    m = args.recorte
    x0, x1, y0, y1 = int(w * m), int(w * (1 - m)), int(h * m), int(h * (1 - m))

    frames = []
    n = 0
    while n < int(args.hasta * fps):
        ok, f = cap.read()
        if not ok:
            break
        H = est.update(f)  # fotograma 0 -> fotograma actual
        alineado = cv2.warpPerspective(f, np.linalg.inv(H), (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        frames.append(cv2.resize(alineado[y0:y1, x0:x1], (w, h), interpolation=cv2.INTER_LINEAR))
        n += 1
    cap.release()
    print(f"{len(frames)} fotogramas alineados; movimiento no estimado en {est.perdidos}")

    args.salida.mkdir(parents=True, exist_ok=True)
    video_out = args.salida / "camara1_estatica.mp4"
    out = cv2.VideoWriter(str(video_out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames + frames[-2:0:-1]:  # ida y vuelta: el bucle no tiene saltos
        out.write(f)
    out.release()

    spaces = [{"id": k, "polygon": v} for k, v in CAJONES.items()]
    cfg = {
        "model": "models/yolov8n.pt",
        "imgsz": 1280,
        "cameras": [
            {"id": "CAM-01", "source": "../demo/camara1_estatica.mp4", "interval_s": 0.5, "conf": 0.35, "occupied_ratio": 0.3, "footprint": 0.6, "confirm_occupied": 2, "confirm_free": 5, "spaces": spaces},
        ],
    }
    (args.salida / "cameras_demo.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    cv2.imwrite(str(args.salida / "camara1_fotograma0.jpg"), frames[0])
    cv2.imwrite(str(args.salida / "camara1_fotograma_final.jpg"), frames[-1])
    print(f"Listo en {args.salida}: camara1_estatica.mp4 ({len(frames) * 2 - 2} fotogramas), cameras_demo.json")


if __name__ == "__main__":
    main()

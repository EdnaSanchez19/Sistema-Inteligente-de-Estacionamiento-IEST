"""Etiqueta a mano qué cajones están ocupados en fotogramas de un video (la "verdad" para medir la precisión).

    python -m parking_vision.tools.etiquetar --config config/cameras.json --camera CAM-01 \
        --video ../datasets/estacionamiento.mp4 --cada 30 --salida ../datasets/etiquetas.csv

Se muestra un fotograma cada `--cada` segundos con los cajones numerados (verde = libre, rojo = ocupado, amarillo =
obstruido: hay un objeto que no es un vehículo dentro del cajón vacío).
Controles: clic en un cajón = cambiar libre → ocupado → obstruido → libre · Enter o espacio = guardar y pasar al siguiente ·
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
from ..occupancy import LIBRE, OBSTRUIDO, OCUPADO, SpaceState

CICLO = {LIBRE: OCUPADO, OCUPADO: OBSTRUIDO, OBSTRUIDO: LIBRE}


def espacio_en(x: float, y: float, spaces: list[Space]) -> int | None:
    """Índice del cajón que contiene el punto (x, y), o None."""
    for i, sp in enumerate(spaces):
        if cv2.pointPolygonTest(sp.polygon.astype(np.float32), (float(x), float(y)), False) >= 0:
            return i
    return None


def _estado(valor: bool | str) -> str:
    return valor if isinstance(valor, str) else OCUPADO if valor else LIBRE


def escribir_filas(path: Path, t: float, spaces: list[Space], estados: list[bool | str]) -> None:
    """Agrega una fila por cajón. `estados`: "libre"/"ocupado"/"obstruido" (o True/False, el formato antiguo)."""
    nuevo = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not nuevo and "estado" not in path.read_text(encoding="utf-8").splitlines()[0]:
        raise SystemExit(f"{path} usa el formato antiguo (sin la columna estado); usa otro archivo de salida.")
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["t_seg", "espacio", "estado", "ocupado"])
        for sp, e in zip(spaces, estados):
            e = _estado(e)
            w.writerow([round(t, 2), sp.id, e, int(e == OCUPADO)])


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
        from ..run import process_frame

        detector = VehicleDetector(cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes, obstacle_classes=cfg.obstacle_classes)

    ocupados: list[str] = []
    win = "Etiquetar (clic = cambiar estado, Enter = guardar, s = saltar, q = salir)"

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            i = espacio_en(x, y, cam.spaces)
            if i is not None:
                ocupados[i] = CICLO[ocupados[i]]

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
            ocupados = [s.estado for s in process_frame(cam, detector, frame)[0]]
        else:
            ocupados = [LIBRE] * len(cam.spaces)
        accion = None
        while accion is None:
            estados = [SpaceState(sp.id, o == OCUPADO, 0.0, None, o == OBSTRUIDO) for sp, o in zip(cam.spaces, ocupados)]
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

"""Prueba controlada del estado "obstruido": inserta objetos en cajones vacíos de un video y mide si el sistema los marca.

    python -m parking_vision.tools.obstaculos_sinteticos --config ../demo/cameras_demo.json --camera CAM-02 \
        --video ../demo/camara2_cctv.mp4 --cada 0.5 \
        --insertar B-27:75:125:persona --insertar B-38:106:140:caja --salida ../salida/con_objetos.mp4

Los videos disponibles no tienen obstrucciones reales (casi nunca hay algo dentro de un cajón vacío), así que se crean:
cada `--insertar CAJON:desde_s:hasta_s:objeto` pega un objeto sobre el cajón durante ese intervalo. La verdad es conocida
(el cajón está "obstruido" en el intervalo) y se compara con lo que reporta el pipeline completo (detección, histéresis y
antirrebote). Objetos: `persona` (recortada del propio video, así que es una persona real de esa cámara), `cono` y `caja`
(dibujados: YOLO no los conoce como clase, así que miden el límite de detectar solo clases COCO).

Es un montaje: sirve para comprobar la lógica y medir retardo y falsos positivos, no para afirmar una precisión real.
"""
from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import cv2
import numpy as np

from ..config import CameraConfig, load_config
from ..detector import VehicleDetector
from .procesar_video import procesar


def recortar_persona(video: Path, detector, min_alto: int = 70) -> np.ndarray:
    """La persona más grande y segura que aparece en el video, recortada con su fondo (un parche rectangular)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    mejor, n = None, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for i in range(0, n, max(1, int(fps))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if not ok:
            break
        for d in detector.detect(f):
            alto = d.y2 - d.y1
            if d.cls == 0 and d.conf >= 0.7 and alto >= min_alto and (mejor is None or alto * d.conf > mejor[0]):
                m = 3
                mejor = (alto * d.conf, f[max(0, int(d.y1) - m): int(d.y2) + m, max(0, int(d.x1) - m): int(d.x2) + m].copy())
    cap.release()
    if mejor is None:
        raise SystemExit("No se encontró una persona clara en el video para usarla como objeto.")
    return mejor[1]


def dibujar_cono(alto: int) -> tuple[np.ndarray, np.ndarray]:
    ancho = max(8, int(alto * 0.62))
    img = np.zeros((alto, ancho, 3), np.uint8)
    mask = np.zeros((alto, ancho), np.uint8)
    tri = np.array([[ancho // 2, 0], [ancho - 2, alto - alto // 8], [2, alto - alto // 8]], np.int32)
    cv2.fillPoly(img, [tri], (30, 110, 245))  # naranja (BGR)
    cv2.fillPoly(mask, [tri], 255)
    cv2.rectangle(img, (0, alto - alto // 8), (ancho - 1, alto - 1), (40, 40, 40), -1)
    cv2.rectangle(mask, (0, alto - alto // 8), (ancho - 1, alto - 1), 255, -1)
    cv2.rectangle(img, (ancho // 4, alto // 3), (3 * ancho // 4, alto // 3 + max(2, alto // 7)), (240, 240, 240), -1)
    return img, mask


def dibujar_caja(alto: int) -> tuple[np.ndarray, np.ndarray]:
    ancho = int(alto * 1.5)
    img = np.full((alto, ancho, 3), (60, 105, 150), np.uint8)  # cartón (BGR)
    cv2.rectangle(img, (0, 0), (ancho - 1, alto // 4), (90, 140, 190), -1)
    cv2.line(img, (ancho // 2, 0), (ancho // 2, alto - 1), (45, 80, 115), max(1, alto // 14))
    cv2.rectangle(img, (0, 0), (ancho - 1, alto - 1), (35, 60, 90), 1)
    return img, np.full((alto, ancho), 255, np.uint8)


def pegar(frame: np.ndarray, parche: np.ndarray, mascara: np.ndarray | None, base_x: int, base_y: int) -> None:
    """Pega el parche con su borde inferior-centro en (base_x, base_y); bordes suavizados."""
    h, w = parche.shape[:2]
    x0, y0 = base_x - w // 2, base_y - h
    H, W = frame.shape[:2]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return
    p = parche[ya - y0: yb - y0, xa - x0: xb - x0]
    m = (mascara if mascara is not None else np.full((h, w), 255, np.uint8))[ya - y0: yb - y0, xa - x0: xb - x0].astype(np.float32) / 255.0
    m = cv2.GaussianBlur(m, (0, 0), 0.8)[..., None]
    frame[ya:yb, xa:xb] = (p * m + frame[ya:yb, xa:xb] * (1 - m)).astype(np.uint8)


def objeto(nombre: str, alto: int, persona: np.ndarray | None):
    if nombre == "persona":
        escala = alto / persona.shape[0]
        return cv2.resize(persona, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA), None
    return dibujar_cono(alto) if nombre == "cono" else dibujar_caja(alto)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/cameras.json")
    ap.add_argument("--camera", required=True)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--insertar", action="append", required=True, help="CAJON:desde_s:hasta_s:persona|cono|caja")
    ap.add_argument("--cada", type=float, default=0.5)
    ap.add_argument("--salida", type=Path, default=None, help="guarda el video con los objetos y la detección")
    ap.add_argument("--alto", type=float, default=2.0, help="alto del objeto en veces el alto del cajón dibujado")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cam: CameraConfig = next(c for c in cfg.cameras if c.id == args.camera)
    detector = VehicleDetector(cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes, obstacle_classes=cfg.obstacle_classes)
    persona = recortar_persona(args.video, detector) if any(i.split(":")[3] == "persona" for i in args.insertar) else None
    plan = []
    for item in args.insertar:
        cajon, t0, t1, nombre = item.split(":")
        sp = next(s for s in cam.spaces if s.id == cajon)
        x, y = sp.polygon[:, 0], sp.polygon[:, 1]
        alto_cajon = float(y.max() - y.min())
        alto = int(min(max(args.alto * alto_cajon, 18), 110)) if nombre == "persona" else int(min(max(0.9 * alto_cajon, 14), 60))
        plan.append((cajon, float(t0), float(t1), nombre, int(x.mean()), int(y.max() - 0.18 * alto_cajon), objeto(nombre, alto, persona)))

    tmp = (args.salida or Path("con_objetos.mp4")).with_suffix(".entrada.mp4")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        t = i / fps
        for _, t0, t1, _, bx, by, (parche, masc) in plan:
            if t0 <= t < t1:
                pegar(f, parche, masc, bx, by)
        out.write(f)
        i += 1
    cap.release()
    out.release()

    cam = dataclasses.replace(cam)
    filas, eventos, _ = procesar(cam, detector, tmp, args.cada, args.salida, None, None, 2.0, None)
    tiempos = sorted({f[0] for f in filas})
    print(f"\nPrueba controlada en {args.camera}: {len(tiempos)} fotogramas, {len(plan)} inserción(es)\n")
    inserciones = {p[0] for p in plan}
    for cajon, t0, t1, nombre, *_ in plan:
        serie = [(f[0], f[3]) for f in filas if f[1] == cajon and t0 <= f[0] < t1]
        obstruido = [t for t, e in serie if e == "obstruido"]
        retardo = (obstruido[0] - t0) if obstruido else None
        tras = [e for f_t, e in [(f[0], f[3]) for f in filas if f[1] == cajon and f[0] >= t1 + 8]]
        liberado = bool(tras) and tras[-1] != "obstruido"
        util = [e for t, e in serie if t >= t0 + 8]  # pasado el tiempo de confirmación
        recall = sum(e == "obstruido" for e in util) / len(util) if util else float("nan")
        print(f"  {cajon} · {nombre:<7} {t0:g}-{t1:g} s: "
              + (f"MARCADO obstruido a los {retardo:.1f} s, recall {recall:.0%}" if obstruido else "NO se marcó (el modelo no reconoció el objeto)")
              + (f"; volvió a libre tras retirarlo" if obstruido and liberado else ("; sigue obstruido tras retirarlo" if obstruido else "")))
    falsos = [(f[0], f[1]) for f in filas if f[3] == "obstruido" and f[1] not in inserciones]
    print(f"  Falsos amarillos en los demás cajones: {len(falsos)} de {len([f for f in filas if f[1] not in inserciones])} observaciones")
    if falsos:
        print("   ", sorted({s for _, s in falsos}))
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

"""Funciones para armar los cajones de una cámara fija a partir de su video (las usan descubrir_cajones y agregar_camara).

Dos fuentes de cajones:
  - Autos estacionados: se detectan con YOLO a lo largo del video y las posiciones que se repiten (no los autos que pasan
    manejando) se vuelven cajones ocupados o que se ocupan y vacían durante el video.
  - Cajones vacíos marcados en el pavimento: se detectan las rayas blancas que los separan y cada par de rayas
    consecutivas encierra un cajón.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def poligono_de_auto(caja) -> list[list[int]]:
    """Cajón de un auto: la mitad inferior de su recuadro, que aproxima dónde toca el suelo."""
    x1, y1, x2, y2 = caja
    ym = y1 + (y2 - y1) * 0.45
    return [[round(x1 + 3), round(ym)], [round(x2 - 3), round(ym)], [round(x2), round(y2)], [round(x1), round(y2)]]


def descubrir_autos(video: Path, modelo: str, cada_s: float = 1.0, min_presencia: float = 0.18, ignorar_y_menor: int = 0,
                    max_solape: float = 0.35, conf: float = 0.35, imgsz: int = 1280):
    """Devuelve (grupos estables, fotogramas analizados, primer fotograma).

    Cada grupo es {"caja": (x1, y1, x2, y2) media, "n": veces vista, "presencia": fracción del video}; los grupos que
    se encima con uno más estable se descartan como duplicados.
    """
    from parking_vision.detector import VehicleDetector

    det = VehicleDetector(modelo, imgsz=imgsz)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    paso = max(1, round(cada_s * fps))
    grupos: list[dict] = []
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
                if d.conf < conf or d.y2 < ignorar_y_menor:
                    continue
                caja = (d.x1, d.y1, d.x2, d.y2)
                mejor = max(grupos, key=lambda g: iou(g["caja"], caja), default=None)
                if mejor and iou(mejor["caja"], caja) >= 0.55:
                    k = mejor["n"]
                    mejor["caja"] = tuple((m * k + c) / (k + 1) for m, c in zip(mejor["caja"], caja))
                    mejor["n"] += 1
                else:
                    grupos.append({"caja": caja, "n": 1})
        i += 1
    cap.release()
    for g in grupos:
        g["presencia"] = round(g["n"] / max(n, 1), 2)
    candidatos = sorted((g for g in grupos if g["n"] / max(n, 1) >= min_presencia), key=lambda g: -g["n"])
    estables: list[dict] = []
    for g in candidatos:
        if all(iou(g["caja"], e["caja"]) < max_solape for e in estables):
            estables.append(g)
    return estables, n, primero


def rayas_blancas(frame: np.ndarray, region: tuple[int, int, int, int], v_min: int = 175, s_max: int = 80, area: tuple[int, int] = (8, 500)) -> list[dict]:
    """Rayas blancas del pavimento dentro de `region` (x1, y1, x2, y2): cada una con sus extremos (arriba, abajo)."""
    x1, y1, x2, y2 = region
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mascara = ((hsv[..., 2] > v_min) & (hsv[..., 1] < s_max)).astype(np.uint8) * 255
    recorte = np.zeros_like(mascara)
    recorte[y1:y2, x1:x2] = 255
    mascara = cv2.bitwise_and(mascara, recorte)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mascara)
    rayas = []
    for i in range(1, n):
        if not (area[0] <= stats[i][4] <= area[1]):
            continue
        ys, xs = np.where(lab == i)
        pts = np.column_stack([xs, ys]).astype(np.float32)
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        t = (pts[:, 0] - x0) * vx + (pts[:, 1] - y0) * vy
        p1, p2 = (x0 + vx * t.min(), y0 + vy * t.min()), (x0 + vx * t.max(), y0 + vy * t.max())
        arriba, abajo = sorted([p1, p2], key=lambda p: p[1])
        if np.hypot(arriba[0] - abajo[0], arriba[1] - abajo[1]) < 5:
            continue
        rayas.append({"arriba": [float(arriba[0]), float(arriba[1])], "abajo": [float(abajo[0]), float(abajo[1])], "cx": float(cent[i][0]), "cy": float(cent[i][1])})
    return rayas


def cajones_entre_rayas(rayas: list[dict], separacion_fila: float = 14.0, hueco: tuple[float, float] = (14.0, 95.0), max_dy: float = 14.0) -> list[list[list[int]]]:
    """Cajones (cuadriláteros) entre rayas consecutivas de la misma fila. Las filas se separan por la altura de las rayas."""
    filas: list[list[dict]] = []
    for r in sorted(rayas, key=lambda r: r["cy"]):
        if filas and abs(r["cy"] - np.mean([x["cy"] for x in filas[-1]])) <= separacion_fila:
            filas[-1].append(r)
        else:
            filas.append([r])
    cajones = []
    for fila in filas:
        fila.sort(key=lambda r: r["cx"])
        for a, b in zip(fila, fila[1:]):
            if hueco[0] <= b["cx"] - a["cx"] <= hueco[1] and abs(a["cy"] - b["cy"]) <= max_dy:
                cajones.append([[round(v) for v in a["abajo"]], [round(v) for v in a["arriba"]], [round(v) for v in b["arriba"]], [round(v) for v in b["abajo"]]])
    return cajones


def es_convexo(poligono) -> bool:
    return bool(cv2.isContourConvex(np.array(poligono, np.int32).reshape(-1, 1, 2)))

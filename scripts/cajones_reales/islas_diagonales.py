"""Extensión de islas_cam02.py para filas en cualquier dirección (camellón en diagonal), como las dos islas de la derecha de CAM-02.

Una fila es: el borde de los cajones junto al camellón (línea quebrada de cerca a lejos), hacia dónde se extiende el cajón (vector de
profundidad, la dirección en que están estacionados los coches) y cómo se achican los cajones al alejarse (el primero mide p0 px a lo largo
del borde y cada uno r veces el anterior). Coordenadas del recorte ampliado de la isla.
    python islas_diagonales.py D        # dibuja la isla y guarda isla_<letra>_cajones.jpg / .json
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

D = Path(__file__).resolve().parents[2] / "datasets" / "reales"

ISLAS = {
    # fila 5 (letra E): la isla de la derecha de la central (recorte isla_b_d.jpg)
    "E": dict(recorte="isla_b_dd.jpg", origen=(1090, 60), zoom=2.4,
              filas=[
                  # fila izquierda: cajones a la izquierda del camellón (su borde es el bordillo amarillo grueso)
                  dict(borde=[(510, 820), (395, 705), (325, 590), (228, 508), (152, 432), (64, 336), (-31, 244), (-120, 164), (-216, 72), (-296, 12)],
                       prof=(-1.0, -0.05), p0=88, r=0.978, largo=1.95),
                  # fila derecha: cajones a la derecha del camellón
                  dict(borde=[(601, 840), (550, 765), (440, 652), (402, 590), (300, 505), (245, 445), (160, 368), (84, 292), (-8, 212), (-80, 140), (-144, 80), (-200, 28)],
                       prof=(1.0, 0.04), p0=88, r=0.978, largo=1.95),
              ], desplazamiento=(480, 48)),  # los bordes están en el recorte anterior (origen (1290, 80)); se desplazan al recorte ancho
}


def punto_en(poli, d):
    pts = np.array(poli, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    d = min(max(d, 0), cum[-1])
    i = min(np.searchsorted(cum, d, side="right") - 1, len(seg) - 1)
    return pts[i] + (d - cum[i]) / seg[i] * (pts[i + 1] - pts[i])


def fila(f, max_cajones=20):
    pts = np.array(f["borde"], float)
    total = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    prof = np.array(f["prof"], float) / np.linalg.norm(f["prof"])
    cajones, d, p = [], 0.0, float(f["p0"])
    for _ in range(max_cajones):
        if d + p * 0.5 > total:
            break
        a, b = punto_en(f["borde"], d), punto_en(f["borde"], d + p)
        largo = f["largo"] * p
        cajones.append([a, b, b + prof * largo, a + prof * largo])
        d += p
        p *= f["r"]
    return cajones


def dibujar(letra):
    cfg = ISLAS[letra]
    img = cv2.imread(str(D / cfg["recorte"]))
    dx, dy = cfg.get("desplazamiento", (0, 0))
    for f in cfg["filas"]:
        f["borde"] = [(x + dx, y + dy) for x, y in f["borde"]]
    filas = [fila(f) for f in cfg["filas"]]
    colores = [(255, 160, 0), (0, 215, 255)]
    for k, lista in enumerate(filas):
        for i, c in enumerate(lista, start=1):
            pts = np.array(c, np.int32)
            cv2.polylines(img, [pts], True, colores[k % 2], 2)
            cx, cy = pts.mean(axis=0).astype(int)
            etiqueta = f"{'IDEF'[k % 4]}{i}"
            cv2.putText(img, etiqueta, (cx - 14, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(img, etiqueta, (cx - 14, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.polylines(img, [np.array(cfg["filas"][k]["borde"], np.int32)], False, (255, 0, 255), 2)
    cv2.imwrite(str(D / f"isla_{letra}_cajones.jpg"), img)
    z, (ox, oy) = cfg["zoom"], cfg["origen"]
    full = lambda p: [round(p[0] / z + ox), round(p[1] / z + oy)]
    salida = []
    for lista in filas:  # primero la fila izquierda y luego la derecha, de lejos a cerca
        for c in reversed(lista):
            salida.append({"polygon": [full(p) for p in c]})
    for n, c in enumerate(salida, start=1):
        c["id"] = f"{letra}-{n:02d}"
    json.dump(salida, open(D / f"isla_{letra}_cajones.json", "w"), indent=1)
    print(f"isla {letra}: " + " + ".join(str(len(f)) for f in filas) + " cajones")


if __name__ == "__main__":
    for letra in sys.argv[1:] or ISLAS:
        dibujar(letra)

"""Cajones de las islas de la cámara general (CAM-02): dos filas por isla, a cada lado de un camellón de árboles, con perspectiva.

Cada isla se define sobre un recorte ampliado (origen y zoom en la imagen de 1920x1080) con sus dos bordillos amarillos (cerca -> lejos) y el
tamaño del cajón en función de la altura: p = K * (y - Y0), calibrado con los coches estacionados de esa isla.
    python islas_cam02.py F G        # dibuja las islas indicadas y guarda <isla>_cajones.jpg / .json
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

D = Path(__file__).resolve().parents[2] / "datasets" / "reales"

ISLAS = {
    # fila 6: la isla central (recorte isla_b5_med.jpg)
    "F": dict(recorte="isla_b5_med.jpg", origen=(860, 60), zoom=2.3, k=0.09, y0=-500.0, largo=2.45, max=18,
              izq=[(482, 872), (330, 440), (195, 48)], der=[(610, 872), (440, 445), (250, 42)]),
    # fila 7: la isla de la izquierda (recorte isla_b_a.jpg)
    "G": dict(recorte="isla_b_a.jpg", origen=(440, 70), zoom=2.4, k=0.118, y0=-115.0, largo=2.55, max=18,
              izq=[(288, 992), (362, 775), (447, 590), (525, 440), (570, 330), (595, 240), (630, 150), (665, 70)],
              der=[(380, 975), (430, 790), (470, 650), (520, 530), (585, 375), (640, 235), (700, 105), (722, 58)]),
}


def x_en(linea, y):
    pts = sorted(linea, key=lambda p: p[1])
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if ya <= y <= yb:
            return xa + (xb - xa) * (y - ya) / (yb - ya)
    return pts[0][0] if y < pts[0][1] else pts[-1][0]


def fila(bordillo, lado, cfg):
    y_cerca, y_lejos = max(p[1] for p in bordillo), min(p[1] for p in bordillo)
    cajones, b = [], float(y_cerca)
    for i in range(cfg["max"]):
        p = cfg["k"] * (b - cfg["y0"]) / (1 + cfg["k"] / 2)
        if b - p * 0.5 < y_lejos:
            break
        ya, yb = b, b - p
        xa, xb = x_en(bordillo, ya), x_en(bordillo, yb)
        largo = cfg["largo"] * p
        cajones.append([(xa, ya), (xb, yb), (xb + lado * largo, yb), (xa + lado * largo, ya)])
        b = yb
    return cajones


def dibujar(letra):
    cfg = ISLAS[letra]
    izq, der = fila(cfg["izq"], -1, cfg), fila(cfg["der"], +1, cfg)
    img = cv2.imread(str(D / cfg["recorte"]))
    for lista, color, pre in ((izq, (255, 160, 0), "I"), (der, (0, 215, 255), "D")):
        for i, c in enumerate(lista, start=1):
            pts = np.array(c, np.int32)
            cv2.polylines(img, [pts], True, color, 2)
            cx, cy = pts.mean(axis=0).astype(int)
            cv2.putText(img, f"{pre}{i}", (cx - 14, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(img, f"{pre}{i}", (cx - 14, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    for linea in (cfg["izq"], cfg["der"]):
        cv2.polylines(img, [np.array(linea, np.int32)], False, (255, 0, 255), 2)
    cv2.imwrite(str(D / f"isla_{letra}_cajones.jpg"), img)
    z, (ox, oy) = cfg["zoom"], cfg["origen"]
    full = lambda p: [round(p[0] / z + ox), round(p[1] / z + oy)]
    # numeración: la fila izquierda primero y luego la derecha, de lejos a cerca (como las filas de la isla 1)
    salida = []
    for lista in (izq, der):
        for c in reversed(lista):  # fila() va de cerca a lejos
            salida.append(({"polygon": [full(p) for p in c]}))
    for n, c in enumerate(salida, start=1):
        c["id"] = f"{letra}-{n:02d}"
    json.dump(salida, open(D / f"isla_{letra}_cajones.json", "w"), indent=1)
    print(f"isla {letra}: {len(izq)} cajones a la izquierda y {len(der)} a la derecha")


if __name__ == "__main__":
    for letra in sys.argv[1:] or ISLAS:
        dibujar(letra)

"""Lateral del gimnasio (CAM-02): la franja de asfalto junto al edificio "Bienvenidos", a la izquierda de la fila 7. 18 cajones.

Se dibujan sobre el recorte ampliado de la cámara general (origen (200, 60) del video de 1920x1080, ampliado 1.9) con `fila` de
islas_diagonales.py: el borde es el bordillo amarillo de la izquierda (de cerca a lejos) y los cajones entran hacia la franja,
perpendiculares al bordillo, achicándose con la perspectiva. GIM-01 es el más cercano a la cámara (junto a los caballetes amarillos).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from islas_diagonales import fila  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN, ZOOM = (200, 60), 1.9
F = dict(borde=[(75, 855), (135, 765), (195, 685), (245, 600), (285, 520), (330, 440), (400, 345), (470, 285), (540, 235), (600, 185), (650, 140), (700, 100)],
         prof=(0.79, 0.61), p0=74, r=0.95, largo=1.6)
cajones = fila(F, max_cajones=18)

if __name__ == "__main__":
    cap = cv2.VideoCapture(str(RAIZ / "datasets" / "reales" / "real_b.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) * 0.5))
    ok, frame = cap.read()
    x1, y1 = ORIGEN
    img = cv2.resize(frame[y1:y1 + 540, x1:x1 + 580], None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_CUBIC)
    salida = []
    for i, c in enumerate(cajones, start=1):
        pts = np.array(c, np.int32)
        cv2.polylines(img, [pts], True, (0, 215, 255), 2)
        cx, cy = pts.mean(axis=0).astype(int)
        cv2.putText(img, str(i), (cx - 8, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, str(i), (cx - 8, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        salida.append({"id": f"GIM-{i:02d}", "polygon": [[round(x / ZOOM + x1), round(y / ZOOM + y1)] for x, y in c]})
    cv2.polylines(img, [np.array(F["borde"], np.int32)], False, (255, 0, 255), 2)
    cv2.imwrite(str(RAIZ / "datasets" / "reales" / "gimnasio_cajones.jpg"), img)
    (RAIZ / "camaras" / "cajones" / "lateral_gimnasio.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")
    print(len(salida), "cajones de la lateral del gimnasio")

"""Lateral de la caseta (CAM-01): 16 cajones en paralelo al bordillo, desde la esquina de las motos hacia la garita.

Se dibuja sobre el recorte ampliado caseta_med.jpg (origen (1500, 0) del video de 2688x1512, ampliado 1.25) y reutiliza `fila` de
islas_diagonales.py: el borde es el bordillo (de cerca a lejos), `prof` apunta hacia la calle y cada cajón mide r veces el anterior.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from islas_diagonales import fila  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
D = RAIZ / "datasets" / "reales"
ORIGEN, ZOOM = (1500, 0), 1.25
F = dict(borde=[(1090, 885), (1000, 785), (900, 675), (800, 570), (700, 470), (620, 410), (520, 340), (420, 270), (330, 215), (240, 165), (150, 125), (70, 100)],
         prof=(-0.57, 0.82), p0=190, r=0.93, largo=0.6)
cajones = fila(F, max_cajones=16)
if __name__ == "__main__":
    img = cv2.imread(str(D / "caseta_med.jpg"))
    salida = []
    for i, c in enumerate(cajones, start=1):  # CAS-01 es el más cercano a las motos
        pts = np.array(c, np.int32)
        cv2.polylines(img, [pts], True, (0, 215, 255), 2)
        cx, cy = pts.mean(axis=0).astype(int)
        cv2.putText(img, str(i), (cx - 10, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, str(i), (cx - 10, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        salida.append({"id": f"CAS-{i:02d}", "polygon": [[round(x / ZOOM + ORIGEN[0]), round(y / ZOOM + ORIGEN[1])] for x, y in c]})
    cv2.polylines(img, [np.array(F["borde"], np.int32)], False, (255, 0, 255), 2)
    cv2.imwrite(str(D / "caseta_cajones.jpg"), img)
    (RAIZ / "camaras" / "cajones" / "lateral_caseta.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")
    print(len(salida), "cajones de la lateral de la caseta")

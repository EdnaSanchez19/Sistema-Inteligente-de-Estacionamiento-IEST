"""Un cajón por cada coche visible (estacionado casi todo el video) en una región de una cámara, con detección por mosaicos y confianza baja.

    python cajon_por_coche.py CAM-01 isla2   |   python cajon_por_coche.py CAM-02 borde
"""
import json, sys
from pathlib import Path
import cv2, numpy as np
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "vision"))
from parking_vision.detector import VehicleDetector
D = R / "datasets" / "reales"
REGIONES = {  # (video, mosaicos, polígono de la región en px del video, prefijo, ancho del recuadro de salida)
    "isla2": ("real_a.mp4", (3, 2), [(0, 170), (660, 170), (660, 300), (480, 470), (440, 620), (0, 820)], "B"),
    "borde": ("real_b.mp4", (3, 2), [(100, 640), (1850, 560), (1850, 1000), (100, 1000)], "X"),
}
def iou(a, b):
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i + 1e-9)
cam, nombre = sys.argv[1], sys.argv[2]
video, mos, region, pref = REGIONES[nombre]
reg = np.array(region, np.float32)
det = VehicleDetector(str(R / "vision" / "models" / "yolov8n.pt"), "cuda:0", 1280, [2, 3, 5, 7], min_conf=0.10)
cap = cv2.VideoCapture(str(D / video)); fps = cap.get(cv2.CAP_PROP_FPS) or 6; paso = max(1, round(2 * fps))
grupos, n, primero, i = [], 0, None, 0
while True:
    ok, f = cap.read()
    if not ok: break
    if i % paso == 0:
        primero = f if primero is None else primero; n += 1
        for d in det.detect(f, mos):
            if d.conf < 0.25: continue
            cx, cy = (d.x1 + d.x2) / 2, d.y2
            if cv2.pointPolygonTest(reg, (float(cx), float(cy)), False) < 0: continue
            caja = (d.x1, d.y1, d.x2, d.y2)
            m = max(grupos, key=lambda g: iou(g["caja"], caja), default=None)
            if m and iou(m["caja"], caja) >= 0.5:
                k = m["n"]; m["caja"] = tuple((a * k + b) / (k + 1) for a, b in zip(m["caja"], caja)); m["n"] += 1
            else: grupos.append({"caja": caja, "n": 1})
    i += 1
est = []
for g in sorted((g for g in grupos if g["n"] / n >= 0.5), key=lambda g: -g["n"]):
    if all(iou(g["caja"], e["caja"]) < 0.3 for e in est): est.append(g)
est.sort(key=lambda g: (round(g["caja"][3] / 50), g["caja"][0]))
img, salida = primero.copy(), []
for k, g in enumerate(est, start=1):
    x1, y1, x2, y2 = g["caja"]; ym = y1 + (y2 - y1) * 0.35
    poly = [[round(x1), round(ym)], [round(x2), round(ym)], [round(x2), round(y2)], [round(x1), round(y2)]]
    salida.append({"id": f"{pref}-{k:02d}", "polygon": poly, "presencia": round(g["n"] / n, 2)})
    cv2.polylines(img, [np.array(poly, np.int32)], True, (0, 215, 255), 3)
    cv2.putText(img, str(k), (int(x1) + 4, int(y2) - 6), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 6, cv2.LINE_AA)
    cv2.putText(img, str(k), (int(x1) + 4, int(y2) - 6), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
cv2.polylines(img, [np.array(region, np.int32)], True, (255, 0, 255), 2)
json.dump(salida, open(D / f"por_coche_{nombre}.json", "w"), indent=1)
cv2.imwrite(str(D / f"por_coche_{nombre}.jpg"), cv2.resize(img, None, fx=0.6, fy=0.6) if img.shape[1] > 2000 else img)
print(nombre, len(salida), "coches estacionados")

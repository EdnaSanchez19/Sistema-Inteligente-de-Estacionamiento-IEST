"""Genera camaras/camaras.json: las 3 cámaras reales del IEST (videos en datasets/reales) a partir de los cajones de camaras/cajones/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
prop = json.loads((ROOT / "camaras" / "cajones" / "propuesta_cam_a.json").read_text(encoding="utf-8"))
# isla 1 (A): fila c dibujada a lo largo de su banqueta (los demás cajones, sin monitoreo); isla 2 (B): provisionales de los coches estacionados
isla1 = json.loads((ROOT / "camaras" / "cajones" / "isla1_c_cajones.json").read_text(encoding="utf-8"))
motos = json.loads((ROOT / "camaras" / "cajones" / "motos_cajones.json").read_text(encoding="utf-8"))  # esquina de motos (8 cajones, motos_cam01.py)
isla1_d = json.loads((ROOT / "camaras" / "cajones" / "isla1_d_cajones.json").read_text(encoding="utf-8"))  # fila d de la isla 1 (fila_d_cam01.py)
cajones_a = [{"id": c["id"], "polygon": c["polygon"]} for c in isla1 + isla1_d] + [{"id": c["id"], "polygon": c["polygon"]} for c in json.loads((ROOT / "camaras" / "cajones" / "por_coche_isla2.json").read_text(encoding="utf-8"))] + [{**m, "detalle_min": 4.5} for m in motos] + json.loads((ROOT / "camaras" / "cajones" / "biblioteca_esquina.json").read_text(encoding="utf-8"))  # tramo de la biblioteca junto a las motos, BIB-19 en adelante (biblioteca_esquina.py)

# filas 3 a 7 de la cámara general: cajones provisionales de los coches estacionados (filas por confirmar)
prop_b = json.loads((ROOT / "camaras" / "cajones" / "propuesta_cam_b.json").read_text(encoding="utf-8"))
# CAM-02 ve las filas de la 4 a la 7 (de derecha a izquierda): la 7 es la isla de la izquierda y la 6 la central, dibujadas a lo largo de su camellón
# (islas_cam02.py); la 4 y la 5 (las de la derecha, con los coches más chicos) siguen con cajones provisionales de los coches estacionados.
cajones_b = []
import cv2
import numpy as np

# fila 5 (letra E): la isla de la derecha de la central, dibujada a lo largo de su camellón en diagonal (islas_diagonales.py)
isla_e = json.loads((ROOT / "camaras" / "cajones" / "isla_E_cajones.json").read_text(encoding="utf-8"))
extremos = json.loads((ROOT / "camaras" / "cajones" / "extremos_cam02.json").read_text(encoding="utf-8"))  # cajones de los extremos (islas 5 y 6)
polis_e = [np.array(c["polygon"], np.float32) for c in isla_e + extremos["E"]]
# fila 4 (letra D, la de más a la derecha): provisional, de los coches estacionados casi todo el video; se omiten los que ya cubre la fila 5
crudos = [c for letra in "CD" for c in prop_b.get(letra, [])]
provisional_d = []
for c in crudos:
    pts = np.array(c["polygon"], np.float32)
    cx, cy = pts.mean(axis=0)
    if any(cv2.pointPolygonTest(pe, (float(cx), float(cy)), False) >= 0 for pe in polis_e):
        continue
    provisional_d.append((round(float(pts[:, 1].max()) / 40), float(pts[:, 0].min()), c["polygon"]))
for n, (_, _, poly) in enumerate(sorted(provisional_d), start=1):
    cajones_b.append({"id": f"D-{n:02d}", "polygon": poly})
cajones_b += [{"id": c["id"], "polygon": c["polygon"]} for c in isla_e + extremos["E"] + extremos["F"]]
# filas 6 (F, la isla central) y 7 (G, la de la izquierda): dos filas por isla dibujadas a lo largo de su camellón (islas_cam02.py)
for letra in "FG":
    cajones_b += [{"id": c["id"], "polygon": c["polygon"]} for c in json.loads((ROOT / "camaras" / "cajones" / f"isla_{letra}_cajones.json").read_text(encoding="utf-8"))]

# lateral de la biblioteca: la hilera junto al bordillo de abajo de la cámara general, con vacíos incluidos (biblioteca_cam02.py)
cajones_b += json.loads((ROOT / "camaras" / "cajones" / "biblioteca_cajones.json").read_text(encoding="utf-8"))

comun = {"interval_s": 1.0, "conf": 0.35, "occupied_ratio": 0.3, "footprint": 0.6, "confirm_occupied": 2, "confirm_free": 5, "confirm_obstruido": 2}
cfg = {
    "model": "models/yolov8n.pt",
    "model_extra": "models/yolov8s.pt",
    "imgsz": 1280,
    "cameras": [
        {"id": "CAM-01", "source": "../datasets/reales/real_a.mp4", **{**comun, "occupied_ratio": 0.22, "mosaicos": [3, 2], "conf_seguimiento": 0.2}, "spaces": cajones_a},   # "Isla 1 y 2" (cajones provisionales)
        {"id": "CAM-02", "source": "../datasets/reales/real_b.mp4", **{**comun, "conf": 0.30, "occupied_ratio": 0.22, "asignar_por_punto": True, "obstaculo_grande": 0.4}, "mosaicos": [3, 2], "conf_seguimiento": 0.2, "spaces": cajones_b},          # "Estacionamiento" (aún sin cajones)
        {"id": "CAM-03", "source": "../datasets/reales/real_c.mp4", **comun, "spaces": []},          # "Entrada": flujo, no vigila cajones
    ],
}
(ROOT / "camaras" / "camaras.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("cajones CAM-01:", len(cajones_a), "| CAM-02:", len(cajones_b))

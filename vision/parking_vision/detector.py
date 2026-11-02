"""Detección de vehículos con YOLO (Ultralytics)."""
from __future__ import annotations

import numpy as np

from .occupancy import Detection


class VehicleDetector:
    """Detecta vehículos y, si se le piden, también objetos que no lo son (`obstacle_classes`) en una sola pasada del modelo."""

    def __init__(self, model_path: str = "yolov8n.pt", device: str | None = None, imgsz: int = 960, classes: tuple[int, ...] = (2, 3, 5, 7), min_conf: float = 0.10, obstacle_classes: tuple[int, ...] = ()):
        from ultralytics import YOLO  # import perezoso: las pruebas de lógica no lo necesitan

        self.model = YOLO(model_path)
        self.device = device
        self.imgsz = imgsz
        self.classes = list(dict.fromkeys([*classes, *obstacle_classes]))
        self.min_conf = min_conf

    def detect(self, frame: np.ndarray, mosaicos: tuple[int, int] | list[int] = (1, 1), traslape: float = 0.2) -> list[Detection]:
        """Devuelve todas las detecciones con confianza >= min_conf (vehículos y obstáculos; `cls` dice cuál es); el filtrado final lo hace quien llama.

        Con `mosaicos` = (columnas, filas) mayor que (1, 1) la imagen se parte en recortes que se traslapan (`traslape`) y cada uno se
        detecta por separado, además de la imagen completa. Los coches lejanos o del lateral miden pocos píxeles y YOLO los pierde si se
        reduce toda la imagen; en un recorte se ven más grandes. Las detecciones se fusionan al final.
        """
        cols, filas = max(1, int(mosaicos[0])), max(1, int(mosaicos[1]))
        if cols * filas == 1:
            return self._predecir([frame], [(0, 0)])[0]
        h, w = frame.shape[:2]
        tw, th = int(w / (cols - (cols - 1) * traslape)), int(h / (filas - (filas - 1) * traslape))
        recortes, origenes = [frame], [(0, 0)]
        for r in range(filas):
            for c in range(cols):
                x0 = 0 if cols == 1 else round(c * (w - tw) / (cols - 1))
                y0 = 0 if filas == 1 else round(r * (h - th) / (filas - 1))
                recortes.append(frame[y0:y0 + th, x0:x0 + tw])
                origenes.append((x0, y0))
        por_recorte = self._predecir(recortes, origenes)
        # recorte que cortó el coche: su caja toca una línea de corte interior del recorte (no el borde de la imagen)
        todas: list[tuple[Detection, bool]] = []
        for i, dets in enumerate(por_recorte):
            ox, oy = origenes[i]
            ancho, alto = recortes[i].shape[1], recortes[i].shape[0]
            for d in dets:
                corta = i > 0 and ((d.x1 - ox < 3 and ox > 0) or (d.y1 - oy < 3 and oy > 0) or (ox + ancho < w - 1 and ox + ancho - d.x2 < 3) or (oy + alto < h - 1 and oy + alto - d.y2 < 3))
                todas.append((d, corta))
        return _fusionar(todas)

    def _predecir(self, imagenes: list[np.ndarray], origenes: list[tuple[int, int]]) -> list[list[Detection]]:
        resultados = self.model.predict(imagenes, conf=self.min_conf, classes=self.classes, imgsz=self.imgsz, device=self.device, verbose=False)
        salida = []
        for res, (ox, oy) in zip(resultados, origenes):
            dets = []
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append(Detection(x1 + ox, y1 + oy, x2 + ox, y2 + oy, float(box.conf[0]), int(box.cls[0])))
            salida.append(dets)
        return salida


class DetectorCombinado:
    """Varios modelos sobre el mismo fotograma: se queda con lo que detecta cualquiera (una detección repetida se queda con la más confiable).

    Cada modelo falla con vehículos distintos: en las cámaras del IEST, YOLOv8s ve los SUV vistos desde arriba y YOLOv8n el sedán blanco.
    """

    def __init__(self, detectores: list["VehicleDetector"]):
        self.detectores = detectores
        self.model = detectores[0].model  # lo que el panel muestra del modelo (dispositivo)
        self.imgsz = detectores[0].imgsz

    def detect(self, frame: np.ndarray, mosaicos: tuple[int, int] | list[int] = (1, 1), traslape: float = 0.2) -> list[Detection]:
        todas = [(d, False) for det in self.detectores for d in det.detect(frame, mosaicos, traslape)]
        return _fusionar(todas)


def _iou_e_inclusion(a: Detection, b: Detection) -> tuple[float, float]:
    """(IoU, intersección / área de la caja más chica)."""
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    area_a, area_b = max((a.x2 - a.x1) * (a.y2 - a.y1), 1e-6), max((b.x2 - b.x1) * (b.y2 - b.y1), 1e-6)
    return inter / (area_a + area_b - inter), inter / min(area_a, area_b)


def _fusionar(todas: list[tuple[Detection, bool]], iou_max: float = 0.5, inclusion: float = 0.8) -> list[Detection]:
    """Quita duplicados entre recortes: la misma clase con IoU alto se queda con la más confiable, y un coche cortado por el borde
    de un recorte se descarta si otra detección más grande ya lo contiene."""
    orden = sorted(todas, key=lambda t: -t[0].conf)
    quedan: list[tuple[Detection, bool]] = []
    for d, corta in orden:
        repetida = False
        for k, _ in quedan:
            iou, incl = _iou_e_inclusion(d, k)
            if (d.cls == k.cls and iou >= iou_max) or (corta and incl >= inclusion and (d.x2 - d.x1) * (d.y2 - d.y1) < (k.x2 - k.x1) * (k.y2 - k.y1)):
                repetida = True
                break
        if not repetida:
            quedan.append((d, corta))
    # un coche completo que llegó después de su pedazo cortado: se quita el pedazo
    finales = []
    for d, corta in quedan:
        if corta and any(o is not d and _iou_e_inclusion(d, o)[1] >= inclusion and (o.x2 - o.x1) * (o.y2 - o.y1) > (d.x2 - d.x1) * (d.y2 - d.y1) for o, _ in quedan):
            continue
        finales.append(d)
    return finales

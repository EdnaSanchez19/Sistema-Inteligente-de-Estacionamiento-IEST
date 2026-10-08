"""Detección de vehículos con YOLO (Ultralytics)."""
from __future__ import annotations

import numpy as np

from .occupancy import Detection


class VehicleDetector:
    def __init__(self, model_path: str = "yolov8n.pt", device: str | None = None, imgsz: int = 960, classes: tuple[int, ...] = (2, 3, 5, 7), min_conf: float = 0.10):
        from ultralytics import YOLO  # import perezoso: las pruebas de lógica no lo necesitan

        self.model = YOLO(model_path)
        self.device = device
        self.imgsz = imgsz
        self.classes = list(classes)
        self.min_conf = min_conf

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Devuelve todas las detecciones con confianza >= min_conf; el filtrado final lo hace quien llama."""
        result = self.model.predict(frame, conf=self.min_conf, classes=self.classes, imgsz=self.imgsz, device=self.device, verbose=False)[0]
        out = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            out.append(Detection(x1, y1, x2, y2, float(box.conf[0]), int(box.cls[0])))
        return out

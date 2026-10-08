"""Detección del colgante, clasificación de su tipo y lectura de su ID (OCR).

Requiere un modelo YOLO propio entrenado con colgantes (`pendant_model` en la configuración);
sin él, este módulo no se activa y el sistema solo reporta ocupación. EasyOCR es opcional.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .occupancy import Detection


@dataclass(frozen=True)
class PendantInfo:
    tipo: str  # nombre de la clase del modelo (estudiante, docente, ...)
    codigo: str | None  # None si el OCR no pudo leerlo
    conf: float


def parse_code(texts: list[str], pattern: str) -> str | None:
    """Devuelve el primer texto del OCR que cumple el formato del ID del colgante."""
    rx = re.compile(pattern)
    for raw in texts:
        cleaned = re.sub(r"[^A-Z0-9-]", "", raw.upper().replace(" ", ""))
        m = rx.fullmatch(cleaned)
        if m:
            return m.group(0)
    return None


def assign_to_vehicles(pendants: list[Detection], vehicles: list[Detection], margin: float = 0.1) -> dict[int, int]:
    """Asocia cada colgante al vehículo cuyo recuadro (ampliado) contiene su centro. {idx_vehiculo: idx_colgante}"""
    result: dict[int, int] = {}
    for pi, p in enumerate(pendants):
        cx, cy = (p.x1 + p.x2) / 2, (p.y1 + p.y2) / 2
        for vi, v in enumerate(vehicles):
            mx, my = (v.x2 - v.x1) * margin, (v.y2 - v.y1) * margin
            if v.x1 - mx <= cx <= v.x2 + mx and v.y1 - my <= cy <= v.y2 + my:
                if vi not in result or p.conf > pendants[result[vi]].conf:
                    result[vi] = pi
                break
    return result


class PendantReader:
    def __init__(self, model_path: str, code_regex: str, device: str | None = None, conf: float = 0.4, use_ocr: bool = True):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.names: dict[int, str] = self.model.names
        self.code_regex = code_regex
        self.device = device
        self.conf = conf
        self._ocr = None
        if use_ocr:
            try:
                import easyocr

                self._ocr = easyocr.Reader(["en"], gpu=device != "cpu", verbose=False)
            except ImportError:
                print("[pendant] easyocr no instalado: se clasifica el tipo pero no se lee el ID")

    def _read_code(self, crop: np.ndarray) -> str | None:
        if self._ocr is None or crop.size == 0:
            return None
        import cv2

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        texts = self._ocr.readtext(gray, detail=0, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
        return parse_code(texts, self.code_regex)

    def read(self, frame: np.ndarray, vehicles: list[Detection]) -> dict[int, PendantInfo]:
        """{índice de vehículo: info del colgante} para los vehículos donde se encontró uno."""
        res = self.model.predict(frame, conf=self.conf, device=self.device, verbose=False)[0]
        pendants, crops = [], []
        for box in res.boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            pendants.append(Detection(x1, y1, x2, y2, float(box.conf[0]), int(box.cls[0])))
            crops.append(frame[max(y1, 0) : max(y2, 0), max(x1, 0) : max(x2, 0)])
        out = {}
        for vi, pi in assign_to_vehicles(pendants, vehicles).items():
            p = pendants[pi]
            out[vi] = PendantInfo(tipo=str(self.names.get(p.cls, p.cls)), codigo=self._read_code(crops[pi]), conf=p.conf)
        return out

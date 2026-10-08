"""Dibujo de resultados sobre el fotograma (verde = libre, rojo = ocupado)."""
from __future__ import annotations

import cv2
import numpy as np

from .config import Space
from .occupancy import Detection, SpaceState

GREEN, RED, YELLOW = (60, 180, 75), (60, 60, 220), (0, 200, 255)


def draw_result(frame: np.ndarray, spaces: list[Space], states: list[SpaceState], detections: list[Detection] | None = None) -> np.ndarray:
    out = frame.copy()
    overlay = frame.copy()
    for sp, st in zip(spaces, states):
        cv2.fillPoly(overlay, [sp.polygon.astype(np.int32)], RED if st.occupied else GREEN)
    out = cv2.addWeighted(overlay, 0.35, out, 0.65, 0)
    for sp, st in zip(spaces, states):
        pts = sp.polygon.astype(np.int32)
        cv2.polylines(out, [pts], True, RED if st.occupied else GREEN, 2)
        cx, cy = pts.mean(axis=0).astype(int)
        cv2.putText(out, sp.id, (cx - 18, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    for d in detections or []:
        cv2.rectangle(out, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), YELLOW, 1)
    libres = sum(not s.occupied for s in states)
    label = f"Libres: {libres}  Ocupados: {len(states) - libres}"
    cv2.rectangle(out, (0, 0), (260, 28), (0, 0, 0), -1)
    cv2.putText(out, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out

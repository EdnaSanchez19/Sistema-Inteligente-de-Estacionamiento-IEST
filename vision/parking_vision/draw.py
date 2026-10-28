"""Dibujo de resultados sobre el fotograma (verde = libre, rojo = ocupado, amarillo = obstruido)."""
from __future__ import annotations

import cv2
import numpy as np

from .config import Space
from .occupancy import Detection, SpaceState

GREEN, RED, YELLOW = (60, 180, 75), (60, 60, 220), (0, 200, 255)  # BGR
VEHICULO = (230, 230, 230)


def _color(st: SpaceState) -> tuple[int, int, int]:
    return RED if st.occupied else YELLOW if st.obstructed else GREEN


def draw_result(frame: np.ndarray, spaces: list[Space], states: list[SpaceState], detections: list[Detection] | None = None) -> np.ndarray:
    out = frame.copy()
    overlay = frame.copy()
    for sp, st in zip(spaces, states):
        cv2.fillPoly(overlay, [sp.polygon.astype(np.int32)], _color(st))
    out = cv2.addWeighted(overlay, 0.35, out, 0.65, 0)
    for sp, st in zip(spaces, states):
        pts = sp.polygon.astype(np.int32)
        cv2.polylines(out, [pts], True, _color(st), 2)
        cx, cy = pts.mean(axis=0).astype(int)
        cv2.putText(out, sp.id, (cx - 18, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        if st.obstructed and st.obstacle_box is not None:  # el objeto que obstruye, marcado en amarillo
            x1, y1, x2, y2 = (int(v) for v in st.obstacle_box)
            cv2.rectangle(out, (x1, y1), (x2, y2), YELLOW, 2, cv2.LINE_AA)
            cv2.putText(out, st.obstacle or "objeto", (x1, max(y1 - 4, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, YELLOW, 1, cv2.LINE_AA)
    for d in detections or []:
        cv2.rectangle(out, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), VEHICULO, 1)
    ocupados = sum(s.occupied for s in states)
    obstruidos = sum(s.obstructed for s in states)
    label = f"Libres: {len(states) - ocupados - obstruidos}  Ocupados: {ocupados}  Obstruidos: {obstruidos}"
    cv2.rectangle(out, (0, 0), (360, 28), (0, 0, 0), -1)
    cv2.putText(out, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out

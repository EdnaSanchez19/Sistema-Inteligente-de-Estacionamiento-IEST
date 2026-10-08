"""Lógica de ocupación: compara vehículos detectados contra las ROI de los cajones.

Es código puro (numpy + OpenCV), sin modelo, para poder probarlo sin GPU ni cámaras.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import Space


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls: int = 2

    def footprint(self, fraction: float) -> np.ndarray:
        """Rectángulo de la parte inferior del recuadro (aprox. donde el vehículo toca el suelo)."""
        top = self.y2 - (self.y2 - self.y1) * fraction
        return np.array([[self.x1, top], [self.x2, top], [self.x2, self.y2], [self.x1, self.y2]], dtype=np.float32)


@dataclass
class SpaceState:
    id: str
    occupied: bool
    confidence: float = 0.0  # confianza de la detección que lo ocupa (0 si está libre)
    detection_index: int | None = None  # índice del vehículo asignado


def _intersection_area(a: np.ndarray, b: np.ndarray) -> float:
    area, _ = cv2.intersectConvexConvex(a.astype(np.float32), b.astype(np.float32))
    return float(area)


def compute_occupancy(
    spaces: list[Space],
    detections: list[Detection],
    occupied_ratio: float = 0.30,
    footprint: float = 0.6,
) -> list[SpaceState]:
    """Marca cada cajón como ocupado/libre.

    Cada vehículo se asigna a un solo cajón: aquel con el que su huella se solapa más. Así un
    auto grande o la perspectiva de la cámara no "ocupan" también a los cajones vecinos. El
    cajón queda ocupado si la huella cubre al menos `occupied_ratio` de su área.
    """
    states = [SpaceState(s.id, False) for s in spaces]
    areas = [max(cv2.contourArea(s.polygon.astype(np.float32)), 1e-6) for s in spaces]

    for di, det in enumerate(detections):
        foot = det.footprint(footprint)
        inter = [_intersection_area(sp.polygon, foot) for sp in spaces]
        if not inter:
            continue
        best = int(np.argmax(inter))
        if inter[best] / areas[best] < occupied_ratio:
            continue
        # Si dos vehículos caen en el mismo cajón, se queda con el más confiable.
        if not states[best].occupied or det.conf > states[best].confidence:
            states[best] = SpaceState(spaces[best].id, True, det.conf, di)
    return states


@dataclass(frozen=True)
class Change:
    space_id: str
    occupied: bool
    previous: bool | None  # None = primera observación


class OccupancyTracker:
    """Antirrebote temporal: un cajón cambia de estado solo tras N observaciones consistentes."""

    def __init__(self, confirm_occupied: int = 2, confirm_free: int = 3):
        self.confirm_occupied = confirm_occupied
        self.confirm_free = confirm_free
        self.state: dict[str, bool] = {}
        self._pending: dict[str, int] = {}

    def update(self, observed: dict[str, bool]) -> list[Change]:
        changes: list[Change] = []
        for sid, obs in observed.items():
            if sid not in self.state:
                self.state[sid] = obs
                self._pending[sid] = 0
                changes.append(Change(sid, obs, None))
                continue
            if obs == self.state[sid]:
                self._pending[sid] = 0
                continue
            self._pending[sid] += 1
            needed = self.confirm_occupied if obs else self.confirm_free
            if self._pending[sid] >= needed:
                changes.append(Change(sid, obs, self.state[sid]))
                self.state[sid] = obs
                self._pending[sid] = 0
        return changes

"""Lógica de ocupación: compara vehículos detectados contra las ROI de los cajones.

Es código puro (numpy + OpenCV), sin modelo, para poder probarlo sin GPU ni cámaras.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import OBSTACULOS_COCO, Space

LIBRE, OCUPADO, OBSTRUIDO = "libre", "ocupado", "obstruido"


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
    confidence: float = 0.0  # confianza de la detección que lo ocupa u obstruye (0 si está libre)
    detection_index: int | None = None  # índice del vehículo asignado
    obstructed: bool = False  # hay un objeto que no es vehículo dentro del cajón vacío
    obstacle: str | None = None  # qué objeto es ("persona", "maleta"...)
    obstacle_box: tuple[float, float, float, float] | None = None

    @property
    def estado(self) -> str:
        """libre / ocupado / obstruido. Un vehículo manda sobre cualquier objeto que haya a su lado o dentro."""
        return OCUPADO if self.occupied else OBSTRUIDO if self.obstructed else LIBRE


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


def compute_states(
    spaces: list[Space],
    vehicles: list[Detection],
    obstacles: list[Detection],
    occupied_ratio: float = 0.30,
    footprint: float = 0.6,
    obstacle_ratio: float = 0.50,
    obstacle_footprint: float = 0.30,
) -> list[SpaceState]:
    """Marca cada cajón como libre, ocupado u obstruido.

    Primero se decide qué cajones tienen un vehículo (`compute_occupancy`). Después, un objeto que no es vehículo
    deja "obstruido" al cajón donde apoya su base (la parte baja de su recuadro) si ese cajón no está ocupado: un
    objeto asignado a un cajón con auto, o que apenas roza el cajón, no cuenta. Cada objeto se asigna a un solo cajón.
    """
    states = compute_occupancy(spaces, vehicles, occupied_ratio, footprint)
    for det in obstacles:
        base = det.footprint(obstacle_footprint)
        base_area = max(cv2.contourArea(base), 1e-6)
        inter = [_intersection_area(sp.polygon, base) for sp in spaces]
        if not inter:
            continue
        best = int(np.argmax(inter))
        st = states[best]
        if st.occupied or inter[best] / base_area < obstacle_ratio:
            continue
        if not st.obstructed or det.conf > st.confidence:
            states[best] = SpaceState(st.id, False, det.conf, None, True, OBSTACULOS_COCO.get(det.cls, "objeto"), (det.x1, det.y1, det.x2, det.y2))
    return states


@dataclass(frozen=True)
class Change:
    space_id: str
    occupied: bool
    previous: bool | None  # None = primera observación
    estado: str = ""  # libre / ocupado / obstruido
    estado_previo: str | None = None


def con_estado_confirmado(states: list[SpaceState], estados: dict[str, str]) -> list[SpaceState]:
    """Estado confirmado por el tracker (con antirrebote) y, de lo observado en este fotograma, el detalle que lo acompaña."""
    out = []
    for s in states:
        e = estados[s.id]
        obstruido = e == OBSTRUIDO
        out.append(SpaceState(s.id, e == OCUPADO, s.confidence, s.detection_index, obstruido, s.obstacle if obstruido else None, s.obstacle_box if obstruido else None))
    return out


def _como_estado(valor: bool | str) -> str:
    """Acepta el valor antiguo (True = ocupado) o el estado en texto."""
    return valor if isinstance(valor, str) else OCUPADO if valor else LIBRE


class OccupancyTracker:
    """Antirrebote temporal: un cajón cambia de estado solo tras N observaciones consistentes del mismo estado nuevo."""

    def __init__(self, confirm_occupied: int = 2, confirm_free: int = 3, confirm_obstructed: int = 6):
        self.confirm = {OCUPADO: confirm_occupied, LIBRE: confirm_free, OBSTRUIDO: confirm_obstructed}
        self.estado: dict[str, str] = {}
        self._cand: dict[str, tuple[str, int]] = {}

    @property
    def state(self) -> dict[str, bool]:
        """Vista booleana (True = ocupado) para quien solo distingue ocupado de lo demás."""
        return {k: v == OCUPADO for k, v in self.estado.items()}

    def update(self, observed: dict[str, bool | str]) -> list[Change]:
        changes: list[Change] = []
        for sid, raw in observed.items():
            obs = _como_estado(raw)
            if sid not in self.estado:
                # Un objeto visto en el primer fotograma puede ser alguien que solo pasa: "obstruido" nunca es el estado
                # inicial, tiene que persistir como cualquier otro cambio (el cajón empieza libre).
                inicial = LIBRE if obs == OBSTRUIDO else obs
                self.estado[sid] = inicial
                if obs != inicial:
                    self._cand[sid] = (obs, 1)
                changes.append(Change(sid, inicial == OCUPADO, None, inicial, None))
                continue
            actual = self.estado[sid]
            if obs == actual:
                self._cand.pop(sid, None)
                continue
            cand, n = self._cand.get(sid, (obs, 0))
            n = n + 1 if cand == obs else 1  # si cambia el estado candidato, la cuenta vuelve a empezar
            if n >= self.confirm[obs]:
                self.estado[sid] = obs
                self._cand.pop(sid, None)
                changes.append(Change(sid, obs == OCUPADO, actual == OCUPADO, obs, actual))
            else:
                self._cand[sid] = (obs, n)
        return changes

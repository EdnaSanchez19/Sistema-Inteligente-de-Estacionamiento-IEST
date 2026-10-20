"""Seguimiento del movimiento de la cámara para que los cajones (ROI) la acompañen.

Una cámara fija real casi no se mueve, pero el viento, la vibración o una toma de dron sí desplazan la imagen.
Se estima, entre fotogramas consecutivos, la homografía del plano del suelo (ORB + RANSAC) y se acumula para
proyectar los cajones dibujados en el primer fotograma sobre el fotograma actual.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import Space


class Estabilizador:
    def __init__(self, min_inliers: int = 40, escala: float = 0.5):
        self.min_inliers = min_inliers
        self.escala = escala
        self.H = np.eye(3)  # coordenadas del fotograma 0 -> coordenadas del fotograma actual
        self._orb = cv2.ORB_create(2500)
        self._bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self._prev: tuple | None = None
        self.perdidos = 0  # fotogramas en los que no se pudo estimar el movimiento

    def _features(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=self.escala, fy=self.escala, interpolation=cv2.INTER_AREA)
        return self._orb.detectAndCompute(gray, None)

    def update(self, frame: np.ndarray) -> np.ndarray:
        """Procesa el siguiente fotograma y devuelve la homografía acumulada fotograma 0 -> actual."""
        kp, des = self._features(frame)
        if self._prev is not None and des is not None and self._prev[1] is not None:
            pares = self._bf.knnMatch(self._prev[1], des, k=2)
            buenos = [p[0] for p in pares if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
            if len(buenos) >= self.min_inliers:
                src = np.float32([self._prev[0][m.queryIdx].pt for m in buenos]) / self.escala
                dst = np.float32([kp[m.trainIdx].pt for m in buenos]) / self.escala
                H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
                if H is not None and int(mask.sum()) >= self.min_inliers:
                    self.H = H @ self.H
                else:
                    self.perdidos += 1
            else:
                self.perdidos += 1
        self._prev = (kp, des)
        return self.H


def proyectar(spaces: list[Space], H: np.ndarray) -> list[Space]:
    """Cajones del fotograma 0 llevados al fotograma actual."""
    out = []
    for sp in spaces:
        pts = cv2.perspectiveTransform(sp.polygon.reshape(-1, 1, 2).astype(np.float32), H).reshape(-1, 2)
        out.append(Space(sp.id, pts.astype(np.float32)))
    return out

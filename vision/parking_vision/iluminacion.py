"""Normalización de la iluminación antes de detectar.

El modelo se entrenó sobre todo con imágenes de día. Cuando el fotograma llega oscuro (noche, tormenta), quemado (sol de frente)
o lavado (niebla) se corrige antes de pasarlo al detector; con luz normal no se toca nada, así que de día el resultado es idéntico
al de no usarlo.

    frame, estado = normalizar(frame)      # estado: "normal", "oscuro", "quemado" o "lavado"

Solo se corrige la luminancia (el canal L de LAB): los colores no cambian, y el fotograma que se muestra en el panel sigue siendo el original.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

NORMAL, OSCURO, QUEMADO, LAVADO = "normal", "oscuro", "quemado", "lavado"


@dataclass(frozen=True)
class AjusteLuz:
    oscuro: float = 70.0  # luminancia media (0-255) por debajo de la cual el fotograma se aclara
    quemado: float = 180.0  # luminancia media por encima de la cual se oscurece
    objetivo: float = 110.0  # luminancia media a la que se lleva (la de los videos de día del IEST está entre 104 y 128)
    lavado_luz: float = 135.0  # un fotograma más claro que esto...
    lavado_contraste: float = 30.0  # ...y con menos contraste (desviación estándar) que esto está lavado: niebla o lente empañado
    clahe_limite: float = 2.0  # cuánto se permite subir el contraste local
    clahe_celdas: int = 8


def medir(frame: np.ndarray) -> tuple[float, float]:
    """(luminancia media, contraste) del fotograma, medidos en una versión reducida: cuesta menos de 1 ms."""
    chico = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    gris = cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY) if chico.ndim == 3 else chico
    return float(gris.mean()), float(gris.std())


def diagnostico(frame: np.ndarray, ajuste: AjusteLuz = AjusteLuz()) -> str:
    if frame is None or frame.size == 0:
        return NORMAL  # sin imagen no hay nada que corregir
    media, contraste = medir(frame)
    if media < ajuste.oscuro:
        return OSCURO
    if media > ajuste.quemado:
        return QUEMADO
    return LAVADO if media > ajuste.lavado_luz and contraste < ajuste.lavado_contraste else NORMAL


def normalizar(frame: np.ndarray, ajuste: AjusteLuz = AjusteLuz()) -> tuple[np.ndarray, str]:
    """Devuelve (fotograma corregido, estado). Con luz normal devuelve el mismo fotograma, sin copiarlo."""
    estado = diagnostico(frame, ajuste)
    if estado == NORMAL:
        return frame, estado
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    luz = lab[:, :, 0]
    if estado == LAVADO:  # estira el rango: lo más oscuro a negro y lo más claro a blanco
        bajo, alto = np.percentile(luz[::4, ::4], (1, 99))
        luz = cv2.convertScaleAbs(luz, alpha=255.0 / max(alto - bajo, 1.0), beta=-bajo * 255.0 / max(alto - bajo, 1.0))
    else:  # curva gamma que lleva la media al objetivo: < 1 aclara, > 1 oscurece
        media = float(np.clip(luz.mean(), 1.0, 254.0))
        gamma = float(np.clip(np.log(ajuste.objetivo / 255.0) / np.log(media / 255.0), 0.3, 3.0))
        luz = cv2.LUT(luz, (np.linspace(0, 1, 256) ** gamma * 255).astype(np.uint8))
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=ajuste.clahe_limite, tileGridSize=(ajuste.clahe_celdas, ajuste.clahe_celdas)).apply(luz)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), estado

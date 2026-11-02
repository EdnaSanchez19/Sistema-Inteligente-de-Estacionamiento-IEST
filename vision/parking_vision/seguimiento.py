"""Seguimiento de vehículos: a cada coche detectado se le da un número que conserva de un fotograma al siguiente.

Sirve para saber cuántos coches hay, cuáles se mueven, cuáles están quietos y desde cuándo, y en qué cajón (si lo hay) están
estacionados, también donde no hay cajones dibujados. Es independiente del estado de los cajones.

No usa el seguimiento de YOLO: el modelo lo comparten todas las cámaras y su estado se mezclaría. Es un emparejamiento simple
entre fotogramas (IoU y, si el coche se movió mucho, distancia entre centros) que basta para coches que se mueven despacio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .occupancy import Detection, Space, _intersection_area

QUIETO = "quieto"
EN_MOVIMIENTO = "en_movimiento"


@dataclass
class Vehiculo:
    id: int
    caja: tuple[float, float, float, float]
    clase: int
    conf: float
    primera_vez: float  # instante (s) en que se vio por primera vez
    ultima_vez: float
    visto: int = 1  # fotogramas en que ha aparecido
    ancla: tuple[float, float] = (0.0, 0.0)  # centro donde empezó a estar quieto
    quieto_desde: float = 0.0
    cajon: str | None = None
    confirmado: bool = False

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.caja[0] + self.caja[2]) / 2, (self.caja[1] + self.caja[3]) / 2)

    def quieto_s(self, ahora: float) -> float:
        return max(0.0, ahora - self.quieto_desde)

    def estado(self, ahora: float, minimo_quieto_s: float) -> str:
        return QUIETO if self.quieto_s(ahora) >= minimo_quieto_s else EN_MOVIMIENTO


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


@dataclass
class SeguidorVehiculos:
    """Un seguidor por cámara. `actualizar` se llama con las detecciones de cada fotograma procesado."""

    iou_min: float = 0.25  # solape mínimo para decir que es el mismo coche
    distancia_max: float = 1.2  # o centros a menos de esta fracción del ancho del coche (coche que se movió bastante entre fotogramas)
    umbral_movimiento: float = 0.22  # el coche "se movió" si su centro se aleja más de esta fracción de su ancho de donde empezó a estar quieto
    minimo_visto: int = 2  # fotogramas para dar por real un vehículo (un falso positivo suelto no cuenta)
    olvidar_s: float = 8.0  # sin verlo durante este tiempo se da por ido
    quieto_minimo_s: float = 6.0  # quieto al menos así de tiempo para llamarlo "quieto"
    _vehiculos: dict[int, Vehiculo] = field(default_factory=dict)
    _siguiente: int = 1

    def reiniciar(self) -> None:
        """Olvida todo (el video volvió a empezar o la cámara perdió la señal): los números nuevos no se confunden con los viejos."""
        self._vehiculos.clear()

    def actualizar(self, detecciones: list[Detection], ahora: float, cajones: list[Space] | None = None) -> list[Vehiculo]:
        """Empareja las detecciones con los vehículos conocidos y devuelve los confirmados que se ven ahora."""
        conocidos = list(self._vehiculos.values())
        costo = np.full((len(conocidos), len(detecciones)), 1e6)
        for i, v in enumerate(conocidos):
            for j, d in enumerate(detecciones):
                caja = (d.x1, d.y1, d.x2, d.y2)
                iou = _iou(v.caja, caja)
                ancho = max(v.caja[2] - v.caja[0], d.x2 - d.x1, 1.0)
                dist = float(np.hypot(v.centro[0] - (d.x1 + d.x2) / 2, v.centro[1] - (d.y1 + d.y2) / 2)) / ancho
                if iou >= self.iou_min:
                    costo[i, j] = 1.0 - iou
                elif dist <= self.distancia_max and d.cls == v.clase:
                    costo[i, j] = 1.0 + dist  # peor que cualquier emparejamiento por solape
        usados_v, usados_d = set(), set()
        if costo.size:
            from scipy.optimize import linear_sum_assignment

            for i, j in zip(*linear_sum_assignment(costo)):
                if costo[i, j] < 1e5:
                    self._asignar(conocidos[i], detecciones[j], ahora)
                    usados_v.add(i)
                    usados_d.add(j)
        for j, d in enumerate(detecciones):
            if j not in usados_d:
                caja = (d.x1, d.y1, d.x2, d.y2)
                v = Vehiculo(self._siguiente, caja, d.cls, d.conf, ahora, ahora, ancla=((d.x1 + d.x2) / 2, (d.y1 + d.y2) / 2), quieto_desde=ahora)
                self._vehiculos[v.id] = v
                self._siguiente += 1
        for v in list(self._vehiculos.values()):
            if ahora - v.ultima_vez > self.olvidar_s:
                del self._vehiculos[v.id]
        visibles = [v for v in self._vehiculos.values() if v.ultima_vez == ahora and v.confirmado]
        if cajones:
            for v in visibles:
                v.cajon = self._cajon_de(v, cajones)
        return visibles

    def _asignar(self, v: Vehiculo, d: Detection, ahora: float) -> None:
        v.caja, v.clase, v.conf, v.ultima_vez = (d.x1, d.y1, d.x2, d.y2), d.cls, d.conf, ahora
        v.visto += 1
        v.confirmado = v.confirmado or v.visto >= self.minimo_visto
        ancho = max(v.caja[2] - v.caja[0], 1.0)
        cx, cy = v.centro
        if np.hypot(cx - v.ancla[0], cy - v.ancla[1]) > self.umbral_movimiento * ancho:
            v.ancla, v.quieto_desde = (cx, cy), ahora  # se movió: vuelve a contar desde cero

    @staticmethod
    def _cajon_de(v: Vehiculo, cajones: list[Space], ocupado_min: float = 0.22) -> str | None:
        x1, y1, x2, y2 = v.caja
        y_huella = y1 + (y2 - y1) * 0.4
        huella = np.array([[x1, y_huella], [x2, y_huella], [x2, y2], [x1, y2]], np.float32)
        areas = [max(cv2.contourArea(s.polygon.astype(np.float32)), 1e-6) for s in cajones]
        inter = [_intersection_area(s.polygon, huella) for s in cajones]
        mejor = int(np.argmax(inter))
        return cajones[mejor].id if inter[mejor] / areas[mejor] >= ocupado_min else None

    def resumen(self, visibles: list[Vehiculo], ahora: float) -> dict:
        quietos = [v for v in visibles if v.estado(ahora, self.quieto_minimo_s) == QUIETO]
        return {"total": len(visibles), "quietos": len(quietos), "en_movimiento": len(visibles) - len(quietos), "fuera_de_cajon": sum(1 for v in quietos if v.cajon is None)}

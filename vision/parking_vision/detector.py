"""Detección de vehículos con YOLO (Ultralytics)."""
from __future__ import annotations

import numpy as np

from .occupancy import Detection


class VehicleDetector:
    """Detecta vehículos y, si se le piden, también objetos que no lo son (`obstacle_classes`) en una sola pasada del modelo."""

    def __init__(self, model_path: str = "yolov8n.pt", device: str | None = None, imgsz: int = 960, classes: tuple[int, ...] = (2, 3, 5, 7), min_conf: float = 0.10, obstacle_classes: tuple[int, ...] = (), half: bool | None = None):
        from ultralytics import YOLO  # import perezoso: las pruebas de lógica no lo necesitan

        self.model = YOLO(model_path)
        self.device = device
        self.imgsz = imgsz
        self.classes = list(dict.fromkeys([*classes, *obstacle_classes]))
        self.min_conf = min_conf
        self.half = _hay_gpu(device) if half is None else bool(half)  # media precisión (FP16): solo sirve en GPU
        self._precision = _args_precision(self.half)

    def detect(self, frame: np.ndarray, mosaicos: tuple[int, int] | list[int] = (1, 1), traslape: float = 0.2, interes: list[tuple[float, float, float, float]] | None = None) -> list[Detection]:
        """Devuelve todas las detecciones con confianza >= min_conf (vehículos y obstáculos; `cls` dice cuál es); el filtrado final lo hace quien llama.

        Con `mosaicos` = (columnas, filas) mayor que (1, 1) la imagen se parte en recortes que se traslapan (`traslape`) y cada uno se
        detecta por separado, además de la imagen completa. Los coches lejanos o del lateral miden pocos píxeles y YOLO los pierde si se
        reduce toda la imagen; en un recorte se ven más grandes. Las detecciones se fusionan al final.

        Con `interes` (rectángulos x1, y1, x2, y2: las zonas donde hay cajones) se saltan los recortes que no tocan ninguno: ahí no hay
        nada que decidir, y la pasada de la imagen completa sigue viendo lo que pase en ellos.
        """
        cols, filas = max(1, int(mosaicos[0])), max(1, int(mosaicos[1]))
        if cols * filas == 1:
            return self._predecir([frame], [(0, 0)])[0]
        h, w = frame.shape[:2]
        recortes, origenes = [frame], [(0, 0)]
        for x0, y0, tw, th in teselas(w, h, cols, filas, traslape):
            if interes is not None and not any(x1 < x0 + tw and x2 > x0 and y1 < y0 + th and y2 > y0 for x1, y1, x2, y2 in interes):
                continue
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
        resultados = self.model.predict(imagenes, conf=self.min_conf, classes=self.classes, imgsz=self.imgsz, device=self.device, verbose=False, **self._precision)
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

    def detect(self, frame: np.ndarray, mosaicos: tuple[int, int] | list[int] = (1, 1), traslape: float = 0.2, interes: list[tuple[float, float, float, float]] | None = None) -> list[Detection]:
        todas = [(d, False) for det in self.detectores for d in det.detect(frame, mosaicos, traslape, interes)]
        return _fusionar(todas)


def crear_detector(cfg) -> "VehicleDetector | DetectorCombinado":
    """El detector que pide la configuración: el modelo principal y, si hay `model_extra`, los dos combinados."""
    def uno(ruta: str) -> VehicleDetector:
        return VehicleDetector(ruta, cfg.device, cfg.imgsz, cfg.vehicle_classes, obstacle_classes=cfg.obstacle_classes, half=cfg.media_precision)

    return DetectorCombinado([uno(cfg.model), uno(cfg.model_extra)]) if cfg.model_extra else uno(cfg.model)


def _hay_gpu(device: str | None) -> bool:
    """True si el modelo va a correr en una GPU con CUDA (ahí la media precisión acelera sin cambiar el resultado de forma apreciable)."""
    if device is not None and str(device).lower() in ("cpu", "mps"):
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # sin torch (pruebas de lógica) no hay GPU que usar
        return False


def _args_precision(half: bool) -> dict:
    """Argumento con que se le pide media precisión a Ultralytics: `quantize=16` en las versiones nuevas, `half=True` en las anteriores."""
    if not half:
        return {}
    try:
        from ultralytics.cfg import DEFAULT_CFG_DICT

        return {"quantize": 16} if "quantize" in DEFAULT_CFG_DICT else {"half": True}
    except Exception:
        return {"half": True}


def rectangulos_de_interes(spaces, margen: float = 0.0) -> list[tuple[float, float, float, float]]:
    """Rectángulo (x1, y1, x2, y2) que encierra cada cajón, con `margen` píxeles alrededor: lo que `detect` recibe como `interes`."""
    return [(float(s.polygon[:, 0].min()) - margen, float(s.polygon[:, 1].min()) - margen, float(s.polygon[:, 0].max()) + margen, float(s.polygon[:, 1].max()) + margen)
            for s in spaces]


def teselas(w: int, h: int, cols: int, filas: int, traslape: float = 0.2) -> list[tuple[int, int, int, int]]:
    """Recortes (x0, y0, ancho, alto) en que se parte una imagen de w x h: `cols` x `filas`, traslapados para no cortar un coche en la unión."""
    tw, th = int(w / (cols - (cols - 1) * traslape)), int(h / (filas - (filas - 1) * traslape))
    return [(0 if cols == 1 else round(c * (w - tw) / (cols - 1)), 0 if filas == 1 else round(r * (h - th) / (filas - 1)), tw, th)
            for r in range(filas) for c in range(cols)]


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
            if d.x2 <= k.x1 or k.x2 <= d.x1 or d.y2 <= k.y1 or k.y2 <= d.y1:
                continue  # ni se tocan: no hace falta calcular nada (son casi todos los pares)
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

"""Carga de configuración (cámaras, ROI de cajones, parámetros de detección).

Las ROI viven en un JSON, no en el código: si una cámara cambia de posición basta con
volver a dibujarlas con `python -m parking_vision.tools.define_spaces`.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_dotenv(path: str | Path) -> None:
    """Lector mínimo de .env (KEY=VALUE). No pisa variables ya definidas."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def expand_env(text: str) -> str:
    """Sustituye ${VAR} por variables de entorno (para no escribir credenciales RTSP en el JSON)."""

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in os.environ:
            raise KeyError(f"Falta la variable de entorno {name} usada en la configuración")
        return os.environ[name]

    return _ENV_REF.sub(sub, text)


@dataclass
class Space:
    id: str  # coincide con espacios.numero en la BD, p. ej. "A-03"
    polygon: np.ndarray  # (N, 2) float32, en píxeles del fotograma


@dataclass
class CameraConfig:
    id: str  # coincide con camaras.codigo, p. ej. "CAM-01"
    source: str  # URL RTSP, ruta de video/imagen o índice de webcam
    spaces: list[Space]
    interval_s: float = 2.0  # procesa un fotograma cada N segundos
    conf: float = 0.35  # confianza mínima para marcar un cajón como ocupado
    conf_baja: float | None = None  # histéresis: un cajón ya ocupado sigue ocupado mientras haya una detección con al menos esta confianza (por defecto 0.6 x conf)
    occupied_ratio: float = 0.30  # fracción del cajón cubierta para marcarlo ocupado
    footprint: float = 0.6  # parte inferior del recuadro usada como "huella" en el suelo (0-1)
    confirm_occupied: int = 2  # observaciones seguidas para pasar a ocupado
    confirm_free: int = 3  # observaciones seguidas para pasar a libre
    offline_after_s: float = 30.0  # sin fotogramas durante este tiempo => cámara desconectada


@dataclass
class Config:
    cameras: list[CameraConfig]
    api_url: str = "http://localhost:8000"
    api_key: str = ""
    model: str = "yolov8n.pt"
    device: str | None = None  # None = automático (GPU si hay), "cpu", "0"
    imgsz: int = 960
    vehicle_classes: tuple[int, ...] = (2, 3, 5, 7)  # COCO: auto, moto, bus, camión
    pendant_model: str | None = None  # modelo YOLO propio que detecta colgantes (opcional)
    pendant_code_regex: str = r"[A-Z0-9]{2,6}-?\d{3,8}"
    save_low_confidence: bool = False  # guarda fotogramas dudosos para reentrenar (desactivado por defecto)
    low_confidence_dir: str = "frames_baja_confianza"
    low_confidence_range: tuple[float, float] = (0.15, 0.35)
    extra: dict = field(default_factory=dict)


def _space(raw: dict) -> Space:
    poly = np.asarray(raw["polygon"], dtype=np.float32)
    if poly.ndim != 2 or poly.shape[1] != 2 or len(poly) < 3:
        raise ValueError(f"Polígono inválido en el cajón {raw.get('id')}: se requieren >= 3 puntos [x, y]")
    return Space(id=str(raw["id"]), polygon=poly)


def load_config(path: str | Path) -> Config:
    raw = json.loads(expand_env(Path(path).read_text(encoding="utf-8")))
    cam_keys = set(CameraConfig.__dataclass_fields__) - {"spaces"}
    cameras = []
    for c in raw["cameras"]:
        opts = {k: v for k, v in c.items() if k in cam_keys}
        cameras.append(CameraConfig(spaces=[_space(s) for s in c.get("spaces", [])], **opts))
    ids = [s.id for c in cameras for s in c.spaces]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay identificadores de cajón repetidos entre cámaras")

    cfg = Config(cameras=cameras)
    cfg.api_url = os.environ.get("API_URL", raw.get("api_url", cfg.api_url))
    cfg.api_key = os.environ.get("INGEST_API_KEY", raw.get("api_key", ""))
    cfg.model = os.environ.get("YOLO_MODEL", raw.get("model", cfg.model))
    for key in ("device", "imgsz", "pendant_model", "pendant_code_regex", "save_low_confidence", "low_confidence_dir"):
        if key in raw:
            setattr(cfg, key, raw[key])
    if "vehicle_classes" in raw:
        cfg.vehicle_classes = tuple(raw["vehicle_classes"])
    if "low_confidence_range" in raw:
        cfg.low_confidence_range = tuple(raw["low_confidence_range"])
    return cfg


def save_spaces(path: str | Path, camera_id: str, source: str, spaces: list[Space]) -> None:
    """Actualiza (o crea) la cámara `camera_id` en el JSON conservando el resto de la configuración."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"cameras": []}
    entry = next((c for c in raw["cameras"] if c["id"] == camera_id), None)
    if entry is None:
        entry = {"id": camera_id, "source": source}
        raw["cameras"].append(entry)
    entry["spaces"] = [{"id": s.id, "polygon": [[round(float(x), 1), round(float(y), 1)] for x, y in s.polygon]} for s in spaces]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

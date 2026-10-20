"""Regresión del banco de simulación: video con verdad conocida + detector YOLO real + métricas.

Usa el montaje sintético (scripts/crear_video_prueba.py) a partir de una foto de un vehículo. Valida que las
herramientas de simulación funcionan; NO mide la precisión real del detector en un estacionamiento.
"""
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT

from parking_vision.config import load_config
from parking_vision.tools import condiciones
from parking_vision.tools.procesar_video import cargar_etiquetas, procesar

MODELO = ROOT / "vision" / "models" / "yolov8n.pt"
FOTO = ROOT / "datasets" / "ejemplos" / "bus.jpg"

pytestmark = pytest.mark.skipif(not (MODELO.exists() and FOTO.exists()), reason="requiere yolov8n.pt y datasets/ejemplos/bus.jpg")


@pytest.fixture(scope="module")
def banco(tmp_path_factory):
    d = tmp_path_factory.mktemp("sim")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "crear_video_prueba.py"), "--imagen", str(FOTO), "--salida", str(d)], check=True, capture_output=True)
    from parking_vision.detector import VehicleDetector

    cam = load_config(d / "cameras.json").cameras[0]
    return d, cam, VehicleDetector(str(MODELO)), cargar_etiquetas(d / "etiquetas.csv")


def exactitud(cam, detector, video, etiquetas):
    _, eventos, (tp, fp, tn, fn) = procesar(cam, detector, video, 1.0, None, None, etiquetas, 2.0, None)
    return (tp + tn) / (tp + fp + tn + fn), eventos


def test_video_de_dia_se_mide_con_buena_exactitud(banco):
    d, cam, detector, etiquetas = banco
    acc, eventos = exactitud(cam, detector, d / "video.mp4", etiquetas)
    assert acc >= 0.85, f"exactitud {acc:.2f}"
    assert sum(e[2] == "entrada" for e in eventos) == 2 and sum(e[2] == "salida" for e in eventos) == 2


def test_la_noche_simulada_no_mejora_y_el_banco_lo_detecta(banco, tmp_path):
    d, cam, detector, etiquetas = banco
    condiciones.aplicar(d / "video.mp4", "noche", tmp_path / "noche.mp4")
    acc_dia, _ = exactitud(cam, detector, d / "video.mp4", etiquetas)
    acc_noche, _ = exactitud(cam, detector, tmp_path / "noche.mp4", etiquetas)
    assert acc_noche <= acc_dia

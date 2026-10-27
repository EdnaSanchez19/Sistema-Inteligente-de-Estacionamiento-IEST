"""Captura RTSP real contra una cámara simulada con ffmpeg, incluida una caída y la reconexión."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from conftest import ROOT, _free_port, wait_until

from parking_vision.capture import CameraStream

MEDIAMTX = ROOT / "herramientas_externas" / "mediamtx" / "mediamtx.exe"
pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not (MEDIAMTX.exists() or shutil.which("mediamtx")),
    reason="requiere ffmpeg y mediamtx (ver scripts/simular_rtsp.py)",
)


def detener_arbol(proc: subprocess.Popen) -> None:
    """Termina el proceso y sus hijos (en Windows, terminate() deja huérfanos a mediamtx y ffmpeg)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def video(tmp_path):
    ruta = tmp_path / "v.mp4"
    out = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    rng = np.random.default_rng(0)
    for _ in range(50):
        out.write(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8))
    out.release()
    return ruta


def test_captura_rtsp_cae_y_se_reconecta(video):
    puerto = _free_port()
    cam = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "simular_rtsp.py"), "--video", str(video), "--puerto", str(puerto), "--caida-tras", "8", "--pausa", "4"])
    stream = CameraStream(f"rtsp://127.0.0.1:{puerto}/cam1", reconnect_s=1.0)
    try:
        time.sleep(3)  # el servidor y la publicación tardan un instante en quedar listos
        stream.start()
        wait_until(lambda: stream.latest()[0] is not None, timeout=25)
        assert stream.latest()[0].shape == (240, 320, 3)
        assert stream.seconds_since_frame() < 2

        # la cámara se cae: el video deja de llegar y el tiempo sin señal crece
        wait_until(lambda: stream.seconds_since_frame() > 3, timeout=30)
        # y vuelve: la captura se reconecta sola
        wait_until(lambda: stream.seconds_since_frame() < 1.5, timeout=40)
    finally:
        stream.stop()
        detener_arbol(cam)

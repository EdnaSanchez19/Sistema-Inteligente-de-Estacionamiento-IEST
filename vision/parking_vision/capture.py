"""Captura de video (RTSP, archivo, webcam o imagen) con reconexión automática."""
from __future__ import annotations

import os
import threading
import time

import cv2
import numpy as np

# RTSP por TCP: más estable que UDP si hay pérdida de paquetes en la LAN/WiFi (no pisa lo que el usuario ya haya definido).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


class CameraStream:
    """Lee en un hilo y conserva solo el último fotograma, para no acumular retraso con RTSP."""

    def __init__(self, source: str, reconnect_s: float = 5.0):
        self.source = source
        self.reconnect_s = reconnect_s
        self._frame: np.ndarray | None = None
        self._frame_time = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._static = False

    def start(self) -> "CameraStream":
        img = cv2.imread(self.source) if not self.source.isdigit() and not self.source.lower().startswith("rtsp") else None
        if img is not None:  # imagen fija (útil para pruebas sin cámara)
            self._frame, self._frame_time, self._static = img, time.time(), True
        else:
            self._thread.start()
        return self

    def _open(self) -> cv2.VideoCapture:
        src: int | str = int(self.source) if self.source.isdigit() else self.source
        return cv2.VideoCapture(src, cv2.CAP_FFMPEG) if isinstance(src, str) and src.startswith("rtsp") else cv2.VideoCapture(src)

    def _run(self) -> None:
        while not self._stop.is_set():
            cap = self._open()
            if not cap.isOpened():
                cap.release()
                self._stop.wait(self.reconnect_s)
                continue
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break  # se perdió la señal: reabrir
                with self._lock:
                    self._frame, self._frame_time = frame, time.time()
            cap.release()
            self._stop.wait(self.reconnect_s)

    def latest(self) -> tuple[np.ndarray | None, float]:
        """(último fotograma, instante en que llegó). El fotograma se entrega una copia."""
        with self._lock:
            return (None if self._frame is None else self._frame.copy()), self._frame_time

    def seconds_since_frame(self) -> float:
        if self._static:
            return 0.0
        with self._lock:
            return float("inf") if self._frame_time == 0 else time.time() - self._frame_time

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

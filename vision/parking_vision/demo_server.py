"""Servidor de visión en modo demostración.

    cd vision
    python -m parking_vision.demo_server --config ../demo/cameras_demo.json

Procesa videos en bucle como si fueran cámaras: detecta vehículos con YOLO, calcula la ocupación de cada cajón,
la publica en la API (igual que el servidor real) y emite el video anotado por HTTP (MJPEG) para el panel web:

  http://127.0.0.1:8100/stream/CAM-01     video en vivo con detecciones y cajones
  http://127.0.0.1:8100/estado            estadísticas del modelo (JSON)

El video emitido no lleva autenticación: úsalo solo en tu red local y para demostraciones.
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from .config import CameraConfig, Config, load_config, load_dotenv
from .detector import VehicleDetector
from .draw import draw_result
from .occupancy import OBSTRUIDO, OCUPADO, Detection, OccupancyTracker, SpaceState, con_estado_confirmado
from .publisher import ApiPublisher
from .run import process_frame

log = logging.getLogger("demo")
CAFE, NARANJA = (35, 47, 106), (40, 140, 242)  # BGR de los colores institucionales aproximados
REAJUSTE_BUCLE_S = 10.0  # segundos de reajuste silencioso tras reiniciar un video en bucle
FPS_EMISION = 15  # el video emitido va a este ritmo como máximo; la detección no depende de él


class CamaraDemo:
    """Una "cámara": reproduce un video en bucle, detecta con YOLO en otro hilo y emite el video anotado."""

    def __init__(self, cam: CameraConfig, cfg: Config, detector: VehicleDetector, det_lock: threading.Lock, publisher: ApiPublisher | None, modelo: str):
        self.cam, self.cfg, self.detector, self.det_lock, self.publisher, self.modelo = cam, cfg, detector, det_lock, publisher, modelo
        self.tracker = OccupancyTracker(cam.confirm_occupied, cam.confirm_free, cam.confirm_obstruido)
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._cond = threading.Condition()
        self._resultado: tuple[list[SpaceState], list[Detection]] = ([], [])
        self.stats: dict = {}
        self._lat: list[float] = []
        self._stop = threading.Event()
        self.fps_video = 25.0
        self.resolucion = ""
        self.calentando_hasta = time.time() + cam.calentamiento_s  # al arrancar y en cada reinicio del video
        self._espectadores = 0  # clientes mirando el video: sin nadie, no se dibuja ni se comprime (ahorra CPU para el modelo)
        self._esp_lock = threading.Lock()

    # --- hilos -------------------------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._reproducir, daemon=True, name=f"{self.cam.id}-video").start()
        threading.Thread(target=self._inferir, daemon=True, name=f"{self.cam.id}-yolo").start()

    def stop(self) -> None:
        self._stop.set()

    def espectador(self):
        """Contexto que cuenta a un cliente mirando el video mientras dure."""
        cam = self

        class _Espectador:
            def __enter__(self):
                with cam._esp_lock:
                    cam._espectadores += 1

            def __exit__(self, *exc):
                with cam._esp_lock:
                    cam._espectadores -= 1

        return _Espectador()

    def _reproducir(self) -> None:
        """Lee el video a su velocidad real, dibuja el resultado más reciente y codifica el JPEG."""
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self.cam.source)
            if not cap.isOpened():
                log.error("%s: no se pudo abrir %s", self.cam.id, self.cam.source)
                self._stop.wait(2)
                continue
            self.fps_video = cap.get(cv2.CAP_PROP_FPS) or 25.0
            self.resolucion = f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
            t_next = time.time()
            salto = max(1, round(self.fps_video / FPS_EMISION))
            n_cuadro = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    # Fin del video: al volver a empezar la escena "salta" (los autos aparecen o desaparecen de golpe),
                    # lo cual no son entradas ni salidas reales; el estado se reajusta en silencio unos segundos.
                    self.calentando_hasta = max(self.calentando_hasta, time.time() + REAJUSTE_BUCLE_S)
                    break
                with self._lock:
                    self._frame = frame
                n_cuadro += 1
                if self._espectadores > 0 and n_cuadro % salto == 0:
                    states, dets = self._resultado
                    vista = self._dibujar(frame, states, dets)
                    ok_jpg, buf = cv2.imencode(".jpg", vista, [cv2.IMWRITE_JPEG_QUALITY, 78])
                    if ok_jpg:
                        with self._cond:
                            self._jpeg = buf.tobytes()
                            self._cond.notify_all()
                t_next += 1.0 / self.fps_video
                espera = t_next - time.time()
                if espera > 0:
                    time.sleep(espera)
                else:
                    t_next = time.time()
            cap.release()

    def _inferir(self) -> None:
        cam = self.cam
        if self.publisher:
            self.publisher.camera_status(cam.id, True)
        ultimo_envio = 0.0
        ultimo_modelo = 0.0
        while not self._stop.wait(cam.interval_s):
            with self._lock:
                frame = None if self._frame is None else self._frame.copy()
            if frame is None:
                continue
            t0 = time.time()
            with self.det_lock:
                states, vehicles, _ = process_frame(cam, self.detector, frame, self.tracker.state)
            ms = (time.time() - t0) * 1000
            self._lat = (self._lat + [ms])[-20:]
            changes = self.tracker.update({s.id: s.estado for s in states})
            confirmados = con_estado_confirmado(states, self.tracker.estado)
            self._resultado = (confirmados, vehicles)
            ocupados = sum(s.occupied for s in confirmados)
            obstruidos = sum(s.obstructed for s in confirmados)
            libres = len(confirmados) - ocupados - obstruidos
            self.stats = {
                "camara": cam.id, "modelo": self.modelo, "dispositivo": str(self.detector.model.device), "imgsz": self.detector.imgsz,
                "fps_video": round(self.fps_video, 1), "fps_deteccion": round(1000 / (sum(self._lat) / len(self._lat)), 1) if self._lat else 0.0,
                "latencia_ms": round(sum(self._lat) / len(self._lat), 1), "vehiculos": len(vehicles), "libres": libres,
                "ocupados": ocupados, "obstruidos": obstruidos, "espacios": len(confirmados), "resolucion": self.resolucion, "umbral_confianza": cam.conf,
                "ids": [s.id for s in confirmados],  # cajones que esta cámara vigila de verdad
            }
            for c in changes:
                if c.estado_previo is not None:
                    log.info("%s %s -> %s", cam.id, c.space_id, c.estado.upper() if c.estado != "libre" else "libre")
            if self.publisher:
                ahora = time.time()
                if changes or ahora - ultimo_envio >= 10:
                    payload = [self._item(s) for s in confirmados]
                    if self.publisher.occupancy(cam.id, payload, calentamiento=ahora < self.calentando_hasta):
                        ultimo_envio = ahora
                if ahora - ultimo_modelo >= 2:
                    if self.publisher.model_stats(self.stats):
                        ultimo_modelo = ahora

    @staticmethod
    def _item(s: SpaceState) -> dict:
        item = {"numero": s.id, "ocupado": s.occupied, "estado": s.estado, "confianza": round(s.confidence, 3) if s.estado != "libre" else None}
        if s.obstructed and s.obstacle:
            item["objeto"] = s.obstacle
        return item

    # --- dibujo y emisión --------------------------------------------------------------------
    def _dibujar(self, frame: np.ndarray, states: list[SpaceState], dets: list[Detection]) -> np.ndarray:
        if states:
            out = draw_result(frame, self.cam.spaces, states, None)
        else:
            out = frame.copy()
        for d in dets:  # recuadros finos de los vehículos detectados (el amarillo queda para los obstruidos)
            cv2.rectangle(out, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), (230, 230, 230), 1, cv2.LINE_AA)
        h, w = out.shape[:2]
        cv2.rectangle(out, (0, 0), (w, 34), (20, 14, 12), -1)
        cv2.circle(out, (18, 17), 6, (60, 60, 230), -1)
        s = self.stats
        texto = f"{self.cam.id}  EN VIVO"
        if s:
            texto += f"   |   {s['modelo']}  {s['latencia_ms']:.0f} ms  |   {s['vehiculos']} vehiculos  |   {s['libres']} libres / {s['ocupados']} ocupados / {s.get('obstruidos', 0)} obstruidos"
        cv2.putText(out, texto, (34, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return out

    def esperar_jpeg(self, ultimo: bytes | None, timeout: float = 2.0) -> bytes | None:
        with self._cond:
            self._cond.wait_for(lambda: self._jpeg is not None and self._jpeg is not ultimo, timeout)
            return self._jpeg


def crear_manejador(camaras: dict[str, CamaraDemo]):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silencia el log por petición
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            ruta = self.path.split("?")[0].rstrip("/")
            if ruta == "/estado":
                return self._json({k: c.stats for k, c in camaras.items()})
            partes = ruta.strip("/").split("/")
            if len(partes) == 2 and partes[0] in ("stream", "snapshot") and partes[1].removesuffix(".jpg") in camaras:
                cam = camaras[partes[1].removesuffix(".jpg")]
                if partes[0] == "snapshot":
                    with cam.espectador():
                        jpg = cam.esperar_jpeg(None, 5)
                    if not jpg:
                        return self._json({"error": "sin imagen"}, 503)
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(jpg)))
                    self.end_headers()
                    self.wfile.write(jpg)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                ultimo = None
                try:
                    with cam.espectador():
                        while True:
                            jpg = cam.esperar_jpeg(ultimo)
                            if jpg is None or jpg is ultimo:
                                continue
                            ultimo = jpg
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
            self._json({"error": "no encontrado", "camaras": list(camaras)}, 404)

    return Manejador


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="../demo/cameras_demo.json")
    ap.add_argument("--host", default="127.0.0.1", help="usa 0.0.0.0 para verlo desde otros equipos de la red")
    ap.add_argument("--puerto", type=int, default=8100)
    ap.add_argument("--sin-api", action="store_true", help="no publica a la API (solo emite el video)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    cfg = load_config(args.config)
    publisher = None if args.sin_api else ApiPublisher(cfg.api_url, cfg.api_key)
    if publisher and not cfg.api_key:
        raise SystemExit("Falta INGEST_API_KEY (variable de entorno o .env)")

    detector = VehicleDetector(cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes, obstacle_classes=cfg.obstacle_classes)
    modelo = Path(cfg.model).stem.replace("yolov", "YOLOv")  # yolov8n -> YOLOv8n
    det_lock = threading.Lock()
    disponibles = []
    for c in cfg.cameras:
        if Path(c.source).exists():
            disponibles.append(c)
        else:
            log.warning("%s: no existe el video %s; se omite esa cámara", c.id, c.source)
    if not disponibles:
        raise SystemExit("Ninguna cámara tiene video. Corre scripts/preparar_demo.py")
    camaras = {c.id: CamaraDemo(c, cfg, detector, det_lock, publisher, modelo) for c in disponibles}
    for c in camaras.values():
        c.start()

    servidor = ThreadingHTTPServer((args.host, args.puerto), crear_manejador(camaras))
    servidor.daemon_threads = True
    log.info("Demostración lista: %s cámara(s). Video en http://%s:%d/stream/<CAM>  (Ctrl+C para salir)", len(camaras), args.host, args.puerto)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for c in camaras.values():
            c.stop()


if __name__ == "__main__":
    main()

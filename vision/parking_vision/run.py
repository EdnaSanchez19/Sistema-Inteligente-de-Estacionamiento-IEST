"""Servidor de procesamiento: un hilo por cámara.

    cd vision
    python -m parking_vision.run --config config/cameras.json              # producción
    python -m parking_vision.run --config config/cameras.json --dry-run    # sin API, imprime cambios
    python -m parking_vision.run --config config/cameras.json --once --out salida/   # 1 fotograma por cámara
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

import cv2

from .capture import CameraStream
from .config import CameraConfig, Config, load_config, load_dotenv
from .detector import VehicleDetector
from .draw import draw_result
from .occupancy import Detection, OccupancyTracker, SpaceState, compute_occupancy
from .pendant import PendantInfo, PendantReader
from .publisher import ApiPublisher

log = logging.getLogger("vision")

HEARTBEAT_S = 60.0  # reenvía el estado completo aunque no haya cambios (la API lo usa como "señal de vida")
LOW_CONF_MIN_GAP_S = 30.0
LOW_CONF_MAX_FILES = 500


def process_frame(cam: CameraConfig, detector: VehicleDetector, frame) -> tuple[list[SpaceState], list[Detection], list[Detection]]:
    """Devuelve (estado de cada cajón, vehículos confiables, todas las detecciones incluso dudosas)."""
    all_dets = detector.detect(frame)
    vehicles = [d for d in all_dets if d.conf >= cam.conf]
    states = compute_occupancy(cam.spaces, vehicles, cam.occupied_ratio, cam.footprint)
    return states, vehicles, all_dets


class CameraWorker(threading.Thread):
    def __init__(self, cam: CameraConfig, cfg: Config, detector: VehicleDetector, det_lock: threading.Lock, pendants: PendantReader | None, publisher: ApiPublisher | None):
        super().__init__(daemon=True, name=cam.id)
        self.cam, self.cfg = cam, cfg
        self.detector, self.det_lock, self.pendants, self.publisher = detector, det_lock, pendants, publisher
        self.stream = CameraStream(cam.source)
        self.stop_event = threading.Event()
        self.tracker = OccupancyTracker(cam.confirm_occupied, cam.confirm_free)
        self._last_low_conf = 0.0

    def stop(self) -> None:
        self.stop_event.set()

    def _payload(self, states: list[SpaceState], pend: dict[int, PendantInfo]) -> list[dict]:
        by_id = {s.id: s for s in states}
        out = []
        for sid, occupied in self.tracker.state.items():
            st = by_id[sid]
            item = {"numero": sid, "ocupado": occupied, "confianza": round(st.confidence, 3) if occupied else None}
            info = pend.get(st.detection_index) if (occupied and st.detection_index is not None) else None
            if info:
                item.update(colgante_tipo=info.tipo, colgante_codigo=info.codigo)
            out.append(item)
        return out

    def _maybe_save_low_conf(self, frame, all_dets: list[Detection]) -> bool:
        lo, hi = self.cfg.low_confidence_range
        if not any(lo <= d.conf < min(hi, self.cam.conf) for d in all_dets):
            return False
        now = time.time()
        if now - self._last_low_conf < LOW_CONF_MIN_GAP_S:
            return False
        self._last_low_conf = now
        if self.cfg.save_low_confidence:
            folder = Path(self.cfg.low_confidence_dir)
            folder.mkdir(parents=True, exist_ok=True)
            if len(list(folder.glob("*.jpg"))) < LOW_CONF_MAX_FILES:
                cv2.imwrite(str(folder / f"{self.cam.id}_{int(now)}.jpg"), frame)
        return True

    def run(self) -> None:
        cam = self.cam
        self.stream.start()
        online: bool | None = None
        last_send = 0.0
        while not self.stop_event.wait(cam.interval_s):
            is_online = self.stream.seconds_since_frame() <= cam.offline_after_s
            if is_online != online:
                online = is_online
                log.info("%s %s", cam.id, "en línea" if online else "SIN SEÑAL")
                if self.publisher:
                    self.publisher.camera_status(cam.id, online)
            frame, _ = self.stream.latest()
            if not is_online or frame is None:
                continue
            try:
                with self.det_lock:
                    states, vehicles, all_dets = process_frame(cam, self.detector, frame)
                    pend = self.pendants.read(frame, vehicles) if self.pendants else {}
            except Exception:
                log.exception("%s: fallo al procesar el fotograma", cam.id)
                continue
            changes = self.tracker.update({s.id: s.occupied for s in states})
            for c in changes:
                if c.previous is not None:
                    log.info("%s %s -> %s", cam.id, c.space_id, "OCUPADO" if c.occupied else "libre")
            low_conf = self._maybe_save_low_conf(frame, all_dets)
            if self.publisher and (changes or low_conf or time.time() - last_send >= HEARTBEAT_S):
                if self.publisher.occupancy(cam.id, self._payload(states, pend), baja_confianza=low_conf):
                    last_send = time.time()
        self.stream.stop()


def build(cfg: Config) -> tuple[VehicleDetector, PendantReader | None]:
    detector = VehicleDetector(cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes)
    pendants = PendantReader(cfg.pendant_model, cfg.pendant_code_regex, cfg.device) if cfg.pendant_model else None
    return detector, pendants


def run_once(cfg: Config, out_dir: Path) -> None:
    detector, _ = build(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    for cam in cfg.cameras:
        stream = CameraStream(cam.source).start()
        deadline = time.time() + 15
        frame = None
        while frame is None and time.time() < deadline:
            frame, _ = stream.latest()
            time.sleep(0.2)
        stream.stop()
        if frame is None:
            print(f"{cam.id}: no se obtuvo fotograma de {cam.source!r}")
            continue
        states, vehicles, all_dets = process_frame(cam, detector, frame)
        libres = sum(not s.occupied for s in states)
        print(f"{cam.id}: {libres} libres / {len(states)-libres} ocupados ({len(vehicles)} vehículos)")
        cv2.imwrite(str(out_dir / f"{cam.id}.jpg"), draw_result(frame, cam.spaces, states, vehicles))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/cameras.json")
    ap.add_argument("--dry-run", action="store_true", help="no envía nada a la API")
    ap.add_argument("--once", action="store_true", help="procesa un fotograma por cámara y termina")
    ap.add_argument("--out", default="salida", help="carpeta de imágenes con --once")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    cfg = load_config(args.config)

    if args.once:
        run_once(cfg, Path(args.out))
        return

    publisher = None if args.dry_run else ApiPublisher(cfg.api_url, cfg.api_key)
    if publisher is None:
        log.info("Modo --dry-run: no se envía nada a la API")
    elif not cfg.api_key:
        raise SystemExit("Falta INGEST_API_KEY (variable de entorno o .env)")
    detector, pendants = build(cfg)
    det_lock = threading.Lock()  # un solo modelo en GPU compartido entre cámaras
    workers = [CameraWorker(c, cfg, detector, det_lock, pendants, publisher) for c in cfg.cameras]
    for w in workers:
        w.start()
    log.info("Procesando %d cámara(s). Ctrl+C para salir.", len(workers))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=5)


if __name__ == "__main__":
    main()

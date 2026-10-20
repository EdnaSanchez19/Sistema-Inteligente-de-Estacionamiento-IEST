"""Procesa un video completo con el mismo pipeline que usa el servidor y reporta qué pasó.

    python -m parking_vision.tools.procesar_video --config config/cameras.json --camera CAM-01 \
        --video ../datasets/estacionamiento.mp4 --salida ../salida/resultado.mp4 --csv ../salida/linea_de_tiempo.csv

Sirve para simular una cámara con un video grabado (tareas 4.1, 4.3 y 4.4): genera un video con los
cajones en verde/rojo, una línea de tiempo por cajón y el resumen de entradas y salidas. Si pasas
--etiquetas (CSV `t_seg,espacio,ocupado`) calcula exactitud, precisión, recall y matriz de confusión.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
from collections import defaultdict
from pathlib import Path

import cv2

from ..config import CameraConfig, load_config
from ..detector import VehicleDetector
from ..draw import draw_result
from ..estabilizar import Estabilizador, proyectar
from ..occupancy import OccupancyTracker, compute_occupancy


def cargar_etiquetas(path: Path) -> dict[str, list[tuple[float, bool]]]:
    """{cajón: [(segundo, ocupado), ...]} ordenado por tiempo."""
    out: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["espacio"].strip()].append((float(row["t_seg"]), row["ocupado"].strip() in ("1", "true", "True", "si", "sí")))
    for v in out.values():
        v.sort()
    return out


def etiqueta_en(t: float, etiquetas: list[tuple[float, bool]], tolerancia: float) -> bool | None:
    """Etiqueta más cercana al instante t (None si no hay una a menos de `tolerancia` segundos)."""
    mejor = min(etiquetas, key=lambda e: abs(e[0] - t), default=None)
    return mejor[1] if mejor and abs(mejor[0] - t) <= tolerancia else None


def metricas(tp: int, fp: int, tn: int, fn: int) -> dict[str, float]:
    total = tp + fp + tn + fn
    div = lambda a, b: a / b if b else 0.0  # noqa: E731
    return {"exactitud": div(tp + tn, total), "precision": div(tp, tp + fp), "recall": div(tp, tp + fn), "n": total}


def procesar(cam: CameraConfig, detector, video: Path, cada_s: float, salida: Path | None, csv_path: Path | None, etiquetas: dict | None, tolerancia: float, limite_s: float | None, estabilizar: bool = False):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir el video {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    paso = max(1, round(cada_s * fps))
    writer = None
    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(str(salida), cv2.VideoWriter_fourcc(*"mp4v"), 1.0 / cada_s, (w, h))

    tracker = OccupancyTracker(cam.confirm_occupied, cam.confirm_free)
    estab = Estabilizador() if estabilizar else None
    filas, eventos = [], []
    tp = fp = tn = fn = 0
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % paso == 0:
            t = idx / fps
            if limite_s and t > limite_s:
                break
            spaces = proyectar(cam.spaces, estab.update(frame)) if estab else cam.spaces
            dets = [d for d in detector.detect(frame) if d.conf >= cam.conf]
            states = compute_occupancy(spaces, dets, cam.occupied_ratio, cam.footprint)
            crudo = {s.id: s.occupied for s in states}
            for ch in tracker.update(crudo):
                if ch.previous is not None:
                    eventos.append((t, ch.space_id, "entrada" if ch.occupied else "salida"))
            for sid, ocupado in crudo.items():
                confirmado = tracker.state[sid]
                filas.append((round(t, 2), sid, int(ocupado), int(confirmado)))
                if etiquetas and sid in etiquetas:
                    real = etiqueta_en(t, etiquetas[sid], tolerancia)
                    if real is not None:
                        tp += confirmado and real
                        fp += confirmado and not real
                        fn += (not confirmado) and real
                        tn += (not confirmado) and (not real)
            if writer:
                confirmed_states = [type(s)(s.id, tracker.state[s.id], s.confidence, s.detection_index) for s in states]
                writer.write(draw_result(frame, spaces, confirmed_states, dets))
        idx += 1
    cap.release()
    if estab and estab.perdidos:
        print(f"Aviso: no se pudo estimar el movimiento de la cámara en {estab.perdidos} fotogramas")
    if writer:
        writer.release()
    if csv_path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["t_seg", "espacio", "ocupado_crudo", "ocupado_confirmado"])
            wr.writerows(filas)
    return filas, eventos, (tp, fp, tn, fn)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/cameras.json")
    ap.add_argument("--camera", required=True, help="id de la cámara cuyos cajones y umbrales se usan")
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--model", default=None, help="por defecto el de la configuración")
    ap.add_argument("--cada", type=float, default=1.0, help="segundos entre fotogramas procesados")
    ap.add_argument("--limite", type=float, default=None, help="procesar solo los primeros N segundos")
    ap.add_argument("--salida", type=Path, default=None, help="video con los cajones dibujados")
    ap.add_argument("--csv", type=Path, default=None, help="línea de tiempo por cajón")
    ap.add_argument("--etiquetas", type=Path, default=None, help="CSV t_seg,espacio,ocupado con la verdad (opcional)")
    ap.add_argument("--tolerancia", type=float, default=2.0, help="segundos máximos entre un fotograma y su etiqueta")
    # Para calibrar umbrales sin editar el JSON: prueba varios valores y compara las métricas.
    ap.add_argument("--estabilizar", action="store_true", help="los cajones siguen el movimiento de la cámara (dron, viento, vibración)")
    ap.add_argument("--conf", type=float, default=None, help="sobrescribe la confianza mínima de la cámara")
    ap.add_argument("--ratio", type=float, default=None, help="sobrescribe occupied_ratio")
    ap.add_argument("--footprint", type=float, default=None, help="sobrescribe footprint")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cam = next((c for c in cfg.cameras if c.id == args.camera), None)
    if cam is None:
        raise SystemExit(f"La cámara {args.camera} no está en {args.config}")
    cambios = {k: v for k, v in (("conf", args.conf), ("occupied_ratio", args.ratio), ("footprint", args.footprint)) if v is not None}
    if cambios:
        cam = dataclasses.replace(cam, **cambios)
        print("Parámetros sobrescritos:", cambios)
    detector = VehicleDetector(args.model or cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes)
    etiquetas = cargar_etiquetas(args.etiquetas) if args.etiquetas else None

    filas, eventos, (tp, fp, tn, fn) = procesar(cam, detector, args.video, args.cada, args.salida, args.csv, etiquetas, args.tolerancia, args.limite, args.estabilizar)

    n_inst = len({f[0] for f in filas})
    print(f"{n_inst} fotogramas procesados ({args.cada} s entre cada uno), {len(cam.spaces)} cajones")
    ocup = {s.id: sum(f[3] for f in filas if f[1] == s.id) / max(n_inst, 1) for s in cam.spaces}
    print("Ocupación media por cajón:", ", ".join(f"{k} {v:.0%}" for k, v in ocup.items()))
    print(f"Eventos: {sum(e[2] == 'entrada' for e in eventos)} entradas, {sum(e[2] == 'salida' for e in eventos)} salidas")
    for t, sid, tipo in eventos:
        print(f"  {t:7.1f} s  {sid}  {tipo}")
    if etiquetas:
        m = metricas(tp, fp, tn, fn)
        print(f"\nContra las etiquetas ({m['n']} comparaciones): exactitud {m['exactitud']:.3f}, precisión {m['precision']:.3f}, recall {m['recall']:.3f}")
        print("Matriz de confusión (filas = real, columnas = predicho)")
        print(f"             ocupado   libre\n  ocupado   {tp:8d} {fn:7d}\n  libre     {fp:8d} {tn:7d}")
    if args.salida:
        print(f"\nVideo con resultados: {args.salida}")


if __name__ == "__main__":
    main()

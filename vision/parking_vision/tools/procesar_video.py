"""Procesa un video completo con el mismo pipeline que usa el servidor y reporta qué pasó.

    python -m parking_vision.tools.procesar_video --config config/cameras.json --camera CAM-01 \
        --video ../datasets/estacionamiento.mp4 --salida ../salida/resultado.mp4 --csv ../salida/linea_de_tiempo.csv

Sirve para simular una cámara con un video grabado (tareas 4.1, 4.3 y 4.4): genera un video con los
cajones en verde (libre), rojo (ocupado) y amarillo (obstruido), una línea de tiempo por cajón y el resumen de
entradas y salidas. Usa el mismo procesamiento que el servidor (histéresis y obstáculos incluidos). Si pasas
--etiquetas (CSV `t_seg,espacio,estado`; también vale `ocupado` con 0/1) calcula la matriz de confusión de los tres
estados, con precisión y recall de cada uno.
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
from ..occupancy import LIBRE, OBSTRUIDO, OCUPADO, OccupancyTracker, con_estado_confirmado
from ..run import process_frame

ESTADOS = (LIBRE, OCUPADO, OBSTRUIDO)


def _estado_de_fila(row: dict) -> str:
    if (row.get("estado") or "").strip():
        e = row["estado"].strip().lower()
        if e not in ESTADOS:
            raise ValueError(f"Estado de etiqueta desconocido: {e!r} (usa libre, ocupado u obstruido)")
        return e
    return OCUPADO if row["ocupado"].strip() in ("1", "true", "True", "si", "sí") else LIBRE


def cargar_etiquetas(path: Path) -> dict[str, list[tuple[float, str]]]:
    """{cajón: [(segundo, estado), ...]} ordenado por tiempo. Acepta la columna `estado` o la antigua `ocupado` (0/1)."""
    out: dict[str, list[tuple[float, str]]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["espacio"].strip()].append((float(row["t_seg"]), _estado_de_fila(row)))
    for v in out.values():
        v.sort()
    return out


def etiqueta_en(t: float, etiquetas: list[tuple[float, str]], tolerancia: float) -> str | None:
    """Etiqueta más cercana al instante t (None si no hay una a menos de `tolerancia` segundos)."""
    mejor = min(etiquetas, key=lambda e: abs(e[0] - t), default=None)
    return mejor[1] if mejor and abs(mejor[0] - t) <= tolerancia else None


def metricas(tp: int, fp: int, tn: int, fn: int) -> dict[str, float]:
    total = tp + fp + tn + fn
    div = lambda a, b: a / b if b else 0.0  # noqa: E731
    return {"exactitud": div(tp + tn, total), "precision": div(tp, tp + fp), "recall": div(tp, tp + fn), "n": total}


def matriz_confusion(pares: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """{real: {predicho: cuántas veces}} para los tres estados."""
    m = {r: {p: 0 for p in ESTADOS} for r in ESTADOS}
    for real, predicho in pares:
        m[real][predicho] += 1
    return m


def metricas_por_estado(m: dict[str, dict[str, int]]) -> dict:
    """Exactitud global y, por estado, precisión (de lo que dijo X, cuánto era X) y recall (de lo que era X, cuánto vio)."""
    div = lambda a, b: a / b if b else None  # noqa: E731  (None = no hay casos: no se inventa un 0 %)
    total = sum(sum(f.values()) for f in m.values())
    por_estado = {}
    for e in ESTADOS:
        tp = m[e][e]
        real, dicho = sum(m[e].values()), sum(m[r][e] for r in ESTADOS)
        p, r = div(tp, dicho), div(tp, real)
        por_estado[e] = {"precision": p, "recall": r, "f1": div(2 * p * r, p + r) if p is not None and r is not None else None, "casos": real}
    return {"exactitud": div(sum(m[e][e] for e in ESTADOS), total), "n": total, "por_estado": por_estado}


def imprimir_matriz(m: dict[str, dict[str, int]]) -> None:
    pct = lambda v: "n/d" if v is None else f"{v:.1%}"  # noqa: E731
    r = metricas_por_estado(m)
    print(f"\nContra las etiquetas ({r['n']} comparaciones): exactitud {pct(r['exactitud'])}")
    print("Matriz de confusión (filas = real, columnas = predicho)")
    print("               " + "".join(f"{e:>10}" for e in ESTADOS) + "     casos")
    for real in ESTADOS:
        print(f"  {real:<12} " + "".join(f"{m[real][p]:>10d}" for p in ESTADOS) + f"{r['por_estado'][real]['casos']:>10d}")
    print("  precisión    " + "".join(f"{pct(r['por_estado'][e]['precision']):>10}" for e in ESTADOS))
    print("  recall       " + "".join(f"{pct(r['por_estado'][e]['recall']):>10}" for e in ESTADOS))


def procesar(cam: CameraConfig, detector, video: Path, cada_s: float, salida: Path | None, csv_path: Path | None, etiquetas: dict | None, tolerancia: float, limite_s: float | None, estabilizar: bool = False):
    """Devuelve (línea de tiempo, entradas/salidas/obstrucciones, [(estado real, estado confirmado)])."""
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

    tracker = OccupancyTracker(cam.confirm_occupied, cam.confirm_free, cam.confirm_obstruido)
    estab = Estabilizador() if estabilizar else None
    filas, eventos, pares = [], [], []
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
            # el mismo procesamiento que el servidor, incluida la histéresis con el estado ya confirmado
            states, dets, _ = process_frame(dataclasses.replace(cam, spaces=spaces), detector, frame, tracker.state)
            crudo = {s.id: s.estado for s in states}
            for ch in tracker.update(crudo):
                if ch.estado_previo is None:
                    continue
                if ch.estado_previo == OCUPADO:
                    eventos.append((t, ch.space_id, "salida"))
                elif ch.estado_previo == OBSTRUIDO:
                    eventos.append((t, ch.space_id, "obstruccion_retirada"))
                if ch.estado == OCUPADO:
                    eventos.append((t, ch.space_id, "entrada"))
                elif ch.estado == OBSTRUIDO:
                    eventos.append((t, ch.space_id, "obstruccion"))
            for sid, estado in crudo.items():
                confirmado = tracker.estado[sid]
                filas.append((round(t, 2), sid, estado, confirmado))
                if etiquetas and sid in etiquetas:
                    real = etiqueta_en(t, etiquetas[sid], tolerancia)
                    if real is not None:
                        pares.append((real, confirmado))
            if writer:
                writer.write(draw_result(frame, spaces, con_estado_confirmado(states, tracker.estado), dets))
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
            wr.writerow(["t_seg", "espacio", "estado_crudo", "estado_confirmado"])
            wr.writerows(filas)
    return filas, eventos, pares


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
    ap.add_argument("--etiquetas", type=Path, default=None, help="CSV t_seg,espacio,estado con la verdad (opcional)")
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
    detector = VehicleDetector(args.model or cfg.model, cfg.device, cfg.imgsz, cfg.vehicle_classes, obstacle_classes=cfg.obstacle_classes if cam.detectar_obstaculos else ())
    etiquetas = cargar_etiquetas(args.etiquetas) if args.etiquetas else None

    filas, eventos, pares = procesar(cam, detector, args.video, args.cada, args.salida, args.csv, etiquetas, args.tolerancia, args.limite, args.estabilizar)

    n_inst = len({f[0] for f in filas})
    print(f"{n_inst} fotogramas procesados ({args.cada} s entre cada uno), {len(cam.spaces)} cajones")
    tiempo = {e: {s.id: sum(f[3] == e for f in filas if f[1] == s.id) / max(n_inst, 1) for s in cam.spaces} for e in ESTADOS}
    print("Ocupación media por cajón:", ", ".join(f"{k} {v:.0%}" for k, v in tiempo[OCUPADO].items()))
    if any(tiempo[OBSTRUIDO].values()):
        print("Obstruido (fracción del tiempo):", ", ".join(f"{k} {v:.0%}" for k, v in tiempo[OBSTRUIDO].items() if v))
    cuenta = {k: sum(e[2] == k for e in eventos) for k in ("entrada", "salida", "obstruccion", "obstruccion_retirada")}
    print(f"Eventos: {cuenta['entrada']} entradas, {cuenta['salida']} salidas, {cuenta['obstruccion']} obstrucciones, {cuenta['obstruccion_retirada']} retiradas")
    for t, sid, tipo in eventos:
        print(f"  {t:7.1f} s  {sid}  {tipo}")
    if etiquetas:
        imprimir_matriz(matriz_confusion(pares))
    if args.salida:
        print(f"\nVideo con resultados: {args.salida}")


if __name__ == "__main__":
    main()

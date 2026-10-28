"""Agrega a una cámara los cajones que le faltan: todo coche estacionado que quede fuera de los cajones ya definidos.

    python scripts/completar_cajones.py --camara CAM-02 --imagen revisar.jpg
    python scripts/completar_cajones.py --camara CAM-03 --excluir 0,0,200,150 --min-presencia 0.3

Un coche cuenta como estacionado si YOLO lo ve en el mismo lugar durante al menos `--min-presencia` del video (los que solo
pasan manejando se descartan). Los cajones nuevos se numeran a continuación de los existentes (B-41, B-42...), así que
los anteriores no cambian de número. Revisa siempre la imagen que genera: es una propuesta automática, y un vehículo
detenido en el pasillo o en la calle no es un cajón (con --excluir se descarta una zona).
Después hay que reiniciar el sistema: `iniciar_sistema.py` registra en la base de datos los cajones nuevos.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "vision"))
import cajones_lib as L  # noqa: E402

from parking_vision.occupancy import Detection, _intersection_area  # noqa: E402


def cubierto(caja, polys, footprint=0.6) -> float:
    """Cuánto cubre un cajón existente a este coche: el MENOR de (fracción del cajón que ocupa la huella del coche, fracción de
    la huella que cae dentro del cajón). Así un cajón vecino que solo roza al coche no cuenta como "su" cajón."""
    foot = Detection(*caja, 0.9).footprint(footprint)
    area_huella = max(cv2.contourArea(foot), 1e-6)
    return max((min(_intersection_area(p, foot) / max(cv2.contourArea(p), 1e-6), _intersection_area(p, foot) / area_huella) for p in polys), default=0.0)


def _encima(a, b) -> float:
    """Fracción del polígono más pequeño que cubre el otro."""
    area, _ = cv2.intersectConvexConvex(np.array(a, np.float32), np.array(b, np.float32))
    return float(area) / max(1e-6, min(cv2.contourArea(np.array(a, np.float32)), cv2.contourArea(np.array(b, np.float32))))


def rect(txt: str):
    return tuple(int(v) for v in txt.split(","))


def dentro(poligono, region) -> bool:
    cx, cy = np.mean(np.array(poligono, np.float32), axis=0)
    x1, y1, x2, y2 = region
    return x1 <= cx <= x2 and y1 <= cy <= y2


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camara", required=True)
    ap.add_argument("--min-presencia", type=float, default=0.30)
    ap.add_argument("--excluir", action="append", type=rect, default=[], help="x1,y1,x2,y2 donde no se buscan cajones")
    ap.add_argument("--region-marcas", action="append", type=rect, default=[], help="x1,y1,x2,y2 donde buscar también cajones VACÍOS entre las rayas blancas")
    ap.add_argument("--min-area", type=float, default=120.0, help="área mínima (px²) de un cajón vacío; los muy lejanos son demasiado pequeños para vigilarlos")
    ap.add_argument("--imagen", type=Path, default=None)
    ap.add_argument("--modelo", default=str(ROOT / "vision" / "models" / "yolov8n.pt"))
    ap.add_argument("--sin-regenerar", action="store_true")
    args = ap.parse_args()

    archivo = ROOT / "demo" / f"cajones_{args.camara.lower().replace('-', '')}.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    video = (ROOT / "demo" / Path(datos["video"]).name).resolve()
    existentes = datos["cajones"]
    polys = [np.array(c["polygon"], np.float32) for c in existentes]

    grupos, n, primero = L.descubrir_autos(video, args.modelo, cada_s=2.0, min_presencia=args.min_presencia)
    nuevos = []
    for g in grupos:
        if cubierto(g["caja"], polys) >= 0.30:
            continue
        q = L.poligono_de_auto(g["caja"])
        if not L.es_convexo(q) or cv2.contourArea(np.array(q, np.float32)) < 2 * args.min_area or any(dentro(q, z) for z in args.excluir):
            continue
        if any(L.iou(g["caja"], (min(p[:, 0]), min(p[:, 1]), max(p[:, 0]), max(p[:, 1]))) > 0.35 for p in polys):
            continue
        if any(_encima(q, p) > 0.4 for p in polys):  # ya lo cubre un cajón existente
            continue
        if any(_encima(q, n["polygon"]) > 0.5 for n in nuevos):  # p. ej. la cabina y la caja de un mismo camión
            continue
        nuevos.append({"polygon": q, "presencia": g["presencia"]})
    for region in args.region_marcas:  # cajones vacíos pintados: entre cada par de rayas contiguas de la misma fila
        for q in L.cajones_entre_rayas(L.rayas_blancas(primero, region)):
            a = np.array(q, np.float32)
            if not L.es_convexo(q) or cv2.contourArea(a) < args.min_area or any(dentro(q, z) for z in args.excluir):
                continue
            if any(_encima(q, p) > 0.15 for p in polys) or any(_encima(q, n["polygon"]) > 0.15 for n in nuevos):
                continue
            nuevos.append({"polygon": q, "presencia": 0.0, "vacio": True})
    nuevos.sort(key=lambda c: (round(np.mean([p[1] for p in c["polygon"]]) / 45), np.mean([p[0] for p in c["polygon"]])))  # lejos -> cerca, izquierda -> derecha

    isla = datos["isla"]
    siguiente = max(int(c["id"].split("-")[1]) for c in existentes) + 1
    for k, c in enumerate(nuevos, start=siguiente):
        existentes.append({"id": f"{isla}-{k:02d}", "polygon": [[int(x), int(y)] for x, y in c["polygon"]], "fuente": "marcado vacío (completado)" if c.get("vacio") else "auto del video (completado)"})
    archivo.write_text(json.dumps(datos, indent=1) + "\n", encoding="utf-8")
    print(f"{args.camara}: +{len(nuevos)} cajones (ahora {len(existentes)}) a partir de {n} fotogramas -> {archivo.name}")

    if args.imagen:
        im = primero.copy()
        for c in existentes:
            pts = np.array(c["polygon"], np.int32)
            nuevo = "completado" in c.get("fuente", "")
            cv2.polylines(im, [pts], True, (255, 0, 255) if nuevo else (255, 255, 255), 2 if nuevo else 1)
            cx, cy = pts.mean(axis=0).astype(int)
            cv2.putText(im, c["id"].split("-")[1], (cx - 9, cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(args.imagen), im)
        print(f"Imagen para revisar (magenta = nuevos): {args.imagen}")

    if not args.sin_regenerar:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "preparar_demo.py"), "--video", str(ROOT / "evidencias" / "03_video_ia" / "video_original.mp4")], check=True)


if __name__ == "__main__":
    main()

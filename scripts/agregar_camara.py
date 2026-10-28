"""Agrega una cámara (un video de cámara fija) al sistema: descubre sus cajones y los deja listos para el servidor de visión.

    python scripts/agregar_camara.py --video "C:/ruta/video.mp4" --camara CAM-03 --isla C \
        --region-marcas 380,180,1000,240 --excluir 990,620,1280,720 --imagen revisar.jpg

Qué hace:
  1. Copia el video a demo/<nombre>.mp4 (no se sube al repositorio: es material de terceros).
  2. Descubre los cajones con autos: YOLO sobre todo el video; las posiciones donde un auto se repite (no los que pasan
     manejando) se vuelven cajones. Se priorizan los que cambian de estado durante el video.
  3. Opcional (--region-marcas): detecta las rayas blancas del pavimento en esa zona y arma los cajones VACÍOS entre cada
     par de rayas, para que haya libres y ocupados desde el inicio.
  4. Escribe demo/cajones_<camara>.json y vuelve a generar demo/cameras_demo.json.

Revisa siempre la imagen que genera (--imagen): los cajones se proponen automáticamente y conviene confirmarlos a ojo.
En producción los cajones se dibujan sobre las líneas con `parking_vision.tools.define_spaces`.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cajones_lib as L  # noqa: E402

PARAMETROS = {"interval_s": 1.0, "conf": 0.35, "occupied_ratio": 0.3, "footprint": 0.6, "confirm_occupied": 3, "confirm_free": 6}


def rect(txt: str) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (int(v) for v in txt.split(","))
    return x1, y1, x2, y2


def area(poligono) -> float:
    return float(cv2.contourArea(np.array(poligono, np.float32)))


def solape(a, b) -> float:
    """Fracción del polígono más pequeño que cubre el otro."""
    mask_a = np.zeros((720, 1280), np.uint8)
    mask_b = np.zeros((720, 1280), np.uint8)
    cv2.fillPoly(mask_a, [np.array(a, np.int32)], 1)
    cv2.fillPoly(mask_b, [np.array(b, np.int32)], 1)
    return float((mask_a & mask_b).sum()) / max(1.0, min(mask_a.sum(), mask_b.sum()))


def dentro(poligono, region) -> bool:
    cx, cy = np.mean(np.array(poligono, np.float32), axis=0)
    x1, y1, x2, y2 = region
    return x1 <= cx <= x2 and y1 <= cy <= y2


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--camara", required=True, help="CAM-03, CAM-04, ...")
    ap.add_argument("--isla", required=True, help="letra de la isla que cubre la cámara (A a H)")
    ap.add_argument("--total", type=int, default=40, help="cajones de la cámara (una isla tiene 40)")
    ap.add_argument("--max-vacios", type=int, default=16, help="máximo de cajones vacíos tomados de las rayas")
    ap.add_argument("--region-marcas", action="append", type=rect, default=[], help="x1,y1,x2,y2 donde buscar cajones vacíos marcados (se puede repetir)")
    ap.add_argument("--excluir", action="append", type=rect, default=[], help="x1,y1,x2,y2 que se ignora (reloj de la cámara, etc.)")
    ap.add_argument("--ignorar-y-menor", type=int, default=0, help="descarta autos más arriba (lejos) de esta fila")
    ap.add_argument("--min-presencia", type=float, default=0.18)
    ap.add_argument("--destino-video", type=Path, default=None, help="por defecto demo/<camara>.mp4")
    ap.add_argument("--modelo", default=str(ROOT / "vision" / "models" / "yolov8n.pt"))
    ap.add_argument("--imagen", type=Path, default=None, help="guarda un fotograma con los cajones propuestos")
    ap.add_argument("--sin-regenerar", action="store_true", help="no vuelve a generar demo/cameras_demo.json")
    args = ap.parse_args()

    cam = args.camara.upper()
    destino = args.destino_video or ROOT / "demo" / f"{cam.lower().replace('-', '')}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if args.video.resolve() != destino.resolve():
        shutil.copyfile(args.video, destino)

    estables, n, primero = L.descubrir_autos(destino, args.modelo, min_presencia=args.min_presencia, ignorar_y_menor=args.ignorar_y_menor)
    autos = [{"polygon": L.poligono_de_auto(g["caja"]), "fuente": "autos del video", "presencia": g["presencia"]} for g in estables]
    autos = [a for a in autos if not any(dentro(a["polygon"], z) for z in args.excluir)]

    vacios = []
    for region in args.region_marcas:
        for q in L.cajones_entre_rayas(L.rayas_blancas(primero, region)):
            if L.es_convexo(q) and area(q) >= 120 and not any(solape(q, a["polygon"]) > 0.15 for a in autos) and not any(dentro(q, z) for z in args.excluir):
                vacios.append({"polygon": q, "fuente": "marcado vacío"})
    vacios = sorted(vacios, key=lambda v: -area(v["polygon"]))[: args.max_vacios]

    cupo_autos = args.total - len(vacios)
    dinamicos = [a for a in autos if a["presencia"] < 0.9]
    estaticos = sorted((a for a in autos if a["presencia"] >= 0.9), key=lambda a: -area(a["polygon"]))
    elegidos = (dinamicos + estaticos)[:cupo_autos] + vacios

    centro = lambda c, i: float(np.mean([p[i] for p in c["polygon"]]))  # noqa: E731
    elegidos.sort(key=lambda c: (round(centro(c, 1) / 45), centro(c, 0)))  # lectura: filas de lejos a cerca, izquierda a derecha
    cajones = [{"id": f"{args.isla.upper()}-{k:02d}", "polygon": [[int(x), int(y)] for x, y in c["polygon"]], "fuente": c["fuente"]} for k, c in enumerate(elegidos, start=1)]

    salida = ROOT / "demo" / f"cajones_{cam.lower().replace('-', '')}.json"
    salida.write_text(json.dumps({"camara": cam, "isla": args.isla.upper(), "video": f"../demo/{destino.name}", "parametros": PARAMETROS, "cajones": cajones}, indent=1) + "\n", encoding="utf-8")
    print(f"{cam}: {len(cajones)} cajones ({len(elegidos) - len(vacios)} con autos del video, {len(vacios)} vacíos marcados) en {n} fotogramas -> {salida}")
    if len(cajones) < args.total:
        print(f"Aviso: la cámara vigila {len(cajones)} de los {args.total} cajones de la isla; el resto quedará sin monitoreo.")

    if args.imagen and primero is not None:
        im = primero.copy()
        for c in cajones:
            pts = np.array(c["polygon"], np.int32)
            cv2.polylines(im, [pts], True, (0, 215, 255) if c["fuente"] == "autos del video" else (255, 200, 0), 1)
            cx, cy = pts.mean(axis=0).astype(int)
            cv2.putText(im, c["id"][-2:], (cx - 8, cy + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(args.imagen), im)
        print(f"Imagen para revisar: {args.imagen}")

    if not args.sin_regenerar:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "preparar_demo.py"), "--video", str(ROOT / "evidencias" / "03_video_ia" / "video_original.mp4")], check=True)


if __name__ == "__main__":
    main()

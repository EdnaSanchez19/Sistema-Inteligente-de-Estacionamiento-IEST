"""Saca fotogramas de los videos reales y los pre-marca con el modelo actual, para que una persona corrija las cajas.

    python scripts/etiquetado/preparar_etiquetado.py                  # ~100 fotogramas (40 de real_a, 50 de real_b, 10 de real_c)
    python scripts/etiquetado/preparar_etiquetado.py --a 30 --b 40 --c 5 --conf 0.25

Deja en datasets/etiquetado/ (ignorado por Git: son imágenes de las cámaras del IEST, con personas y placas):
    images/*.jpg   los fotogramas, a la resolución original
    labels/*.txt   una caja por línea en formato YOLO: "clase x_centro y_centro ancho alto" (todo de 0 a 1)
    clases.txt     0 = coche (autos, camionetas, SUV, camiones, autobuses), 1 = moto

Las cajas iniciales son las de los modelos YOLOv8n y YOLOv8s combinados (detección por mosaicos, confianza >= --conf): falta corregirlas (borrar las falsas, dibujar
las que faltan) con `python scripts/etiquetado/etiquetar_coches.py`.
"""
import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision"))
from parking_vision.detector import DetectorCombinado, VehicleDetector  # noqa: E402

CLASES = ["coche", "moto"]
COCO_A_NUESTRA = {2: 0, 3: 1, 5: 0, 7: 0}  # coche, moto, autobús y camión (COCO) -> coche / moto
MOSAICOS = {"real_a": (3, 2), "real_b": (3, 2), "real_c": (1, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", type=int, default=40, help="fotogramas de real_a (cámara 'Fila 1 y 2')")
    ap.add_argument("--b", type=int, default=50, help="fotogramas de real_b (cámara 'Estacionamiento')")
    ap.add_argument("--c", type=int, default=10, help="fotogramas de real_c (cámara 'Entrada')")
    ap.add_argument("--conf", type=float, default=0.25, help="confianza mínima de las cajas iniciales")
    ap.add_argument("--videos", type=Path, default=ROOT / "datasets" / "reales")
    ap.add_argument("--salida", type=Path, default=ROOT / "datasets" / "etiquetado")
    args = ap.parse_args()

    (args.salida / "images").mkdir(parents=True, exist_ok=True)
    (args.salida / "labels").mkdir(parents=True, exist_ok=True)
    (args.salida / "clases.txt").write_text("\n".join(CLASES) + "\n", encoding="utf-8")
    modelos = [m for m in ("yolov8n.pt", "yolov8s.pt") if (ROOT / "vision" / "models" / m).exists()]  # si están los dos se combinan: cada uno ve coches que el otro no
    det = DetectorCombinado([VehicleDetector(str(ROOT / "vision" / "models" / m), "cuda:0", 1280, [2, 3, 5, 7], min_conf=0.10) for m in modelos])

    for nombre, n in (("real_a", args.a), ("real_b", args.b), ("real_c", args.c)):
        cap = cv2.VideoCapture(str(args.videos / f"{nombre}.mp4"))
        if not cap.isOpened():
            print(f"{nombre}: no se pudo abrir {args.videos / (nombre + '.mp4')}, se omite")
            continue
        total, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 6.0
        cajas_total = 0
        for i in range(n):
            idx = int((i + 0.5) / n * total)  # repartidos parejo por todo el video
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            base = f"{nombre}_{int(idx / fps):04d}s"
            cv2.imwrite(str(args.salida / "images" / f"{base}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 93])
            lineas = []
            for d in det.detect(frame, MOSAICOS[nombre]):
                if d.cls in COCO_A_NUESTRA and d.conf >= args.conf:
                    lineas.append(f"{COCO_A_NUESTRA[d.cls]} {(d.x1 + d.x2) / 2 / w:.6f} {(d.y1 + d.y2) / 2 / h:.6f} {(d.x2 - d.x1) / w:.6f} {(d.y2 - d.y1) / h:.6f}")
            (args.salida / "labels" / f"{base}.txt").write_text("\n".join(lineas) + ("\n" if lineas else ""), encoding="utf-8")
            cajas_total += len(lineas)
        cap.release()
        print(f"{nombre}: {n} fotogramas, {cajas_total} cajas iniciales ({cajas_total / max(n, 1):.0f} por fotograma)")
    print(f"Listo en {args.salida}. Siguiente paso: python scripts/etiquetado/etiquetar_coches.py")


if __name__ == "__main__":
    main()

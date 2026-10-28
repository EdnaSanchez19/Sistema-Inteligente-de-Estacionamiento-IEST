"""Arma los 40 cajones de la isla B (cámara CAM-02) para la demostración: ocupados y vacíos.

    python scripts/cajones_cam02.py --candidatos datasets/camara2/cajones_candidatos.json --imagen datasets/camara2/cajones_cam02.jpg

Mezcla dos fuentes, porque lo que importa es poder distinguir cajones vacíos de ocupados:
  - 23 cajones del estacionamiento cercano, donde se ven autos (los descubre scripts/descubrir_cajones.py a partir
    del video; se priorizan los que cambian de estado y los más grandes).
  - 17 cajones del estacionamiento de atrás, que están marcados y vacíos. Se dibujaron entre las rayas blancas del
    pavimento (posiciones medidas sobre el primer fotograma del video de 1280x720).
Escribe demo/cajones_cam02.json, que usa scripts/preparar_demo.py. El video NO se incluye en el repositorio.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# Estacionamiento de atrás, fila cercana: extremos (abajo, arriba) de cada raya blanca, de izquierda a derecha
FILA_2 = [((23, 366), (43, 350)), ((68, 370), (90, 349)), ((121, 369), (134, 348)), ((174, 368), (181, 348)), ((226, 367), (227, 347)),
          ((278, 365), (272, 346)), ((330, 363), (323, 353)), ((382, 361), (363, 343))]
# Fila lejana: separaciones a ojo (x de abajo); cada raya se inclina un poco hacia la derecha a la izquierda de la imagen
FILA_1_X = [33, 70, 110, 149, 189, 228, 264, 300, 337, 372]
Y1_ABAJO, Y1_ARRIBA = 336, 321


def cajones_lejanos() -> list[list[list[int]]]:
    quads = []
    for (b1, t1), (b2, t2) in zip(FILA_2, FILA_2[1:]):  # entre rayas consecutivas
        quads.append([list(b1), list(t1), list(t2), list(b2)])
    for x1, x2 in zip(FILA_1_X, FILA_1_X[1:]):
        s1 = 8 if x1 < 300 else -3
        s2 = 8 if x2 < 300 else -3
        quads.append([[x1, Y1_ABAJO], [x1 + s1, Y1_ARRIBA], [x2 + s2, Y1_ARRIBA], [x2, Y1_ABAJO]])
    return quads


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidatos", required=True, type=Path, help="salida de descubrir_cajones.py")
    ap.add_argument("--cercanos", type=int, default=23)
    ap.add_argument("--isla", default="B")
    ap.add_argument("--salida", type=Path, default=ROOT / "demo" / "cajones_cam02.json")
    ap.add_argument("--imagen", type=Path, default=None)
    args = ap.parse_args()

    cand = json.loads(args.candidatos.read_text(encoding="utf-8"))["cajones"]

    def area(c):
        p = np.array(c["polygon"], np.float32)
        return cv2.contourArea(p)

    def sobre_marca_de_agua(c):  # el reloj "ID: 001" de la cámara tapa la esquina inferior derecha
        xs = [p[0] for p in c["polygon"]]
        ys = [p[1] for p in c["polygon"]]
        return max(xs) > 990 and max(ys) > 630

    validos = [c for c in cand if not sobre_marca_de_agua(c)]
    dinamicos = [c for c in validos if c["presencia"] < 0.9]  # autos que llegan o se van durante el video
    estables = sorted((c for c in validos if c["presencia"] >= 0.9), key=lambda c: -area(c))
    cercanos = (dinamicos + estables)[: args.cercanos]
    lejanos = cajones_lejanos()

    todos = [{"polygon": c["polygon"], "fuente": "autos del video"} for c in cercanos] + [{"polygon": q, "fuente": "marcado vacío"} for q in lejanos]
    centro_y = lambda p: np.mean([q[1] for q in p["polygon"]])  # noqa: E731
    centro_x = lambda p: np.mean([q[0] for q in p["polygon"]])  # noqa: E731
    todos.sort(key=lambda p: (round(centro_y(p) / 45), centro_x(p)))  # orden de lectura: filas de lejos a cerca
    for k, c in enumerate(todos, start=1):
        c["id"] = f"{args.isla}-{k:02d}"
        c["polygon"] = [[int(x), int(y)] for x, y in c["polygon"]]
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps({"camara": "CAM-02", "isla": args.isla, "video": "../demo/camara2_cctv.mp4", "cajones": [{"id": c["id"], "polygon": c["polygon"], "fuente": c["fuente"]} for c in todos]}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(todos)} cajones ({len(cercanos)} con autos del video, {len(lejanos)} marcados vacíos) -> {args.salida}")

    if args.imagen:
        im = cv2.imread(str(ROOT / "datasets" / "camara2" / "f0.jpg"))
        if im is not None:
            for c in todos:
                pts = np.array(c["polygon"], np.int32)
                cv2.polylines(im, [pts], True, (0, 215, 255) if c["fuente"] == "autos del video" else (255, 200, 0), 1)
                cx, cy = pts.mean(axis=0).astype(int)
                cv2.putText(im, c["id"][-2:], (cx - 8, cy + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imwrite(str(args.imagen), im)


if __name__ == "__main__":
    main()

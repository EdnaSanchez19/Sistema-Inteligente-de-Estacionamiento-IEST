"""Herramienta local para corregir las cajas de los coches en los fotogramas de datasets/etiquetado (preparados con preparar_etiquetado.py).

    python scripts/etiquetar_coches.py            # abre http://127.0.0.1:8200 en el navegador

Todo se queda en este equipo: el servidor solo escucha en 127.0.0.1 y las imágenes no salen de datasets/etiquetado. Cada cambio se guarda
solo, en formato YOLO (labels/*.txt), y las imágenes marcadas como revisadas se anotan en revisadas.json.
"""
import argparse
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGINA = Path(__file__).with_name("etiquetador.html")
NOMBRE = re.compile(r"^[A-Za-z0-9_\-]+$")
_cerrojo = threading.Lock()


def crear_manejador(datos: Path):
    imagenes, etiquetas, revisadas = datos / "images", datos / "labels", datos / "revisadas.json"

    def leer_revisadas() -> set[str]:
        try:
            return set(json.loads(revisadas.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, obj, codigo: int = 200) -> None:
            self._responder(codigo, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def _nombre(self, prefijo: str) -> str | None:
            nombre = self.path[len(prefijo):].split("?")[0]
            nombre = nombre[:-4] if nombre.endswith(".jpg") else nombre
            return nombre if NOMBRE.match(nombre) and (imagenes / f"{nombre}.jpg").exists() else None

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._responder(200, PAGINA.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/imagenes":
                rev = leer_revisadas()
                lista = []
                for f in sorted(imagenes.glob("*.jpg")):
                    txt = etiquetas / f"{f.stem}.txt"
                    n = len([1 for linea in txt.read_text(encoding="utf-8").splitlines() if linea.strip()]) if txt.exists() else 0
                    lista.append({"nombre": f.stem, "cajas": n, "revisada": f.stem in rev})
                self._json(lista)
            elif self.path.startswith("/img/"):
                nombre = self._nombre("/img/")
                if nombre:
                    self._responder(200, (imagenes / f"{nombre}.jpg").read_bytes(), "image/jpeg")
                else:
                    self._json({"error": "no existe"}, 404)
            elif self.path.startswith("/api/etiquetas/"):
                nombre = self._nombre("/api/etiquetas/")
                if not nombre:
                    return self._json({"error": "no existe"}, 404)
                cajas = []
                txt = etiquetas / f"{nombre}.txt"
                if txt.exists():
                    for linea in txt.read_text(encoding="utf-8").splitlines():
                        p = linea.split()
                        if len(p) == 5:
                            cajas.append({"c": int(p[0]), "x": float(p[1]), "y": float(p[2]), "w": float(p[3]), "h": float(p[4])})
                self._json(cajas)
            else:
                self._json({"error": "no existe"}, 404)

        def do_PUT(self):
            nombre = self._nombre("/api/etiquetas/") if self.path.startswith("/api/etiquetas/") else None
            if not nombre:
                return self._json({"error": "no existe"}, 404)
            try:
                cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
                lineas = []
                for b in cuerpo["cajas"]:
                    c, x, y, w, h = int(b["c"]), float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"])
                    if c in (0, 1) and 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1:
                        lineas.append(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
                revisada = bool(cuerpo.get("revisada", False))
            except (ValueError, KeyError, TypeError):
                return self._json({"error": "datos inválidos"}, 400)
            with _cerrojo:
                (etiquetas / f"{nombre}.txt").write_text("\n".join(lineas) + ("\n" if lineas else ""), encoding="utf-8")
                rev = leer_revisadas()
                rev.add(nombre) if revisada else rev.discard(nombre)
                revisadas.write_text(json.dumps(sorted(rev)), encoding="utf-8")
            self._json({"guardadas": len(lineas), "revisada": revisada})

    return Manejador


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=ROOT / "datasets" / "etiquetado")
    ap.add_argument("--puerto", type=int, default=8200)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()
    if not (args.datos / "images").is_dir():
        raise SystemExit(f"No hay fotogramas en {args.datos}. Primero: python scripts/preparar_etiquetado.py")
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), crear_manejador(args.datos))
    url = f"http://127.0.0.1:{args.puerto}"
    print(f"Etiquetador en {url} (Ctrl+C para cerrar). Los cambios se guardan solos en {args.datos / 'labels'}")
    if not args.sin_navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrado.")


if __name__ == "__main__":
    main()

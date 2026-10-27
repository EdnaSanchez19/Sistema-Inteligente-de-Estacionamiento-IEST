"""Simula las cámaras publicando ocupación a la API, para demostrar el sistema sin cámaras reales.

    python scripts/simulate_cameras.py --api http://localhost:8000
    python scripts/simulate_cameras.py --api http://localhost:8000 --zonas B,C --hora-simulada 20

Cada auto llega, se queda un tiempo y se va. La duración de la estancia y la ocupación media salen del perfil del
dataset de Kaggle (demo/perfil_ocupacion.json, ver scripts/perfil_dataset.py): estancias de unas 3 horas, con la
forma de la distribución original, y una ocupación cercana al 55 %. Como una demostración no puede esperar horas,
`--hora-simulada` dice cuántos segundos reales dura una hora simulada (30 por defecto).

El 85 % de las llegadas llevan un colgante de los usuarios de muestra (los crea `python -m app.seed --muestra 150`),
con la mezcla de tipos del perfil. Los cajones que ya vigila un servidor de visión real (cameras_demo.json) se
omiten para no pisar lo que detecta el modelo. Usa INGEST_API_KEY del entorno o del .env. Ctrl+C para detener.
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
from app.seed import ZONAS, colgantes_de_muestra  # noqa: E402  (misma distribución de islas y cámaras que la BD inicial)

PERFIL_POR_DEFECTO = {  # valores del dataset de Kaggle, por si no existe demo/perfil_ocupacion.json
    "ocupacion_media": 0.55,
    "duracion_horas": {"0": 0.053, "1": 0.15, "2": 0.238, "3": 0.247, "4": 0.144, "5": 0.102, "6": 0.048, "7": 0.015, "8": 0.001, "10": 0.002},
}


def clave_de_ingesta() -> str:
    if os.environ.get("INGEST_API_KEY"):
        return os.environ["INGEST_API_KEY"]
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("INGEST_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("Falta INGEST_API_KEY (variable de entorno o .env)")


def cajones_vigilados(config: Path) -> set[str]:
    """Cajones que vigila un servidor de visión: los de las cámaras de la configuración cuyo video existe."""
    if not config.is_file():
        return set()
    cfg = json.loads(config.read_text(encoding="utf-8"))
    vigilados: set[str] = set()
    for cam in cfg.get("cameras", []):
        if (ROOT / "vision" / cam["source"]).resolve().exists():
            vigilados |= {s["id"] for s in cam.get("spaces", [])}
    return vigilados


class SimuladorIslas:
    """Llegadas y salidas con la distribución de estancia del perfil. No hace red: devuelve lo que hay que publicar."""

    def __init__(self, camaras: dict[str, list[str]], perfil: dict, hora_s: float, tick_s: float, colgantes: list[tuple[str, object]], rnd: random.Random, prob_colgante: float = 0.85):
        self.camaras, self.hora_s, self.tick_s, self.rnd, self.prob_colgante = camaras, hora_s, tick_s, rnd, prob_colgante
        self.ocupacion = float(perfil["ocupacion_media"])
        horas = perfil["duracion_horas"]
        self._horas, self._pesos = [int(h) for h in horas], [float(p) for p in horas.values()]
        self.media_h = sum(h * p for h, p in zip(self._horas, self._pesos)) / sum(self._pesos) + 0.5  # +0.5: la fracción de hora sorteada
        self.fin: dict[str, float | None] = {n: None for ns in camaras.values() for n in ns}  # None = libre
        self.colgante_de: dict[str, tuple[str, object]] = {}
        self.libres = list(colgantes)
        self.rnd.shuffle(self.libres)
        self.primer_envio = True

    def _duracion_s(self) -> float:
        h = self.rnd.choices(self._horas, self._pesos)[0] + self.rnd.random()
        return h * self.hora_s

    def _llegada(self, numero: str, t: float, item: dict) -> None:
        self.fin[numero] = t + self._duracion_s()
        item["ocupado"], item["confianza"] = True, round(self.rnd.uniform(0.6, 0.98), 2)
        if self.libres and self.rnd.random() < self.prob_colgante:
            codigo, tipo = self.colgante_de[numero] = self.libres.pop()
            item["colgante_codigo"], item["colgante_tipo"] = codigo, getattr(tipo, "value", str(tipo))

    def paso(self, t: float) -> dict[str, list[dict]]:
        """Avanza hasta el instante t. Devuelve {cámara: [cajones que cambiaron]} (todos en el primer envío)."""
        p_llegada = (self.ocupacion / (1 - self.ocupacion)) / (self.media_h * self.hora_s / self.tick_s)  # mantiene la ocupación media
        salida: dict[str, list[dict]] = {}
        for cam, numeros in self.camaras.items():
            items = []
            for n in numeros:
                item = {"numero": n, "ocupado": False, "confianza": None}
                antes = self.fin[n] is not None
                if self.primer_envio:
                    if self.rnd.random() < self.ocupacion:  # estado inicial: la estancia ya va a la mitad
                        self._llegada(n, t, item)
                        self.fin[n] = t + self._duracion_s() * self.rnd.random()
                    items.append(item)
                    continue
                if antes and t >= self.fin[n]:
                    self.fin[n] = None
                    if n in self.colgante_de:
                        self.libres.insert(0, self.colgante_de.pop(n))
                    items.append(item)
                elif not antes and self.rnd.random() < p_llegada:
                    self._llegada(n, t, item)
                    items.append(item)
            if items:
                salida[cam] = items
        self.primer_envio = False
        return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--interval", type=float, default=3.0, help="segundos entre actualizaciones")
    ap.add_argument("--hora-simulada", type=float, default=30.0, help="segundos reales que dura una hora simulada")
    ap.add_argument("--perfil", type=Path, default=ROOT / "demo" / "perfil_ocupacion.json")
    ap.add_argument("--vigilados", type=Path, default=ROOT / "demo" / "cameras_demo.json", help="cajones de esta configuración (si su video existe) no se simulan")
    ap.add_argument("--muestra", type=int, default=150, help="cuántos colgantes de muestra hay en la BD (python -m app.seed --muestra N)")
    ap.add_argument("--zonas", default="", help="solo simula estas islas, p. ej. B,C (por defecto todas)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    perfil = json.loads(args.perfil.read_text(encoding="utf-8")) if args.perfil.is_file() else PERFIL_POR_DEFECTO
    omitir = cajones_vigilados(args.vigilados)
    solo = {z.strip().upper() for z in args.zonas.split(",") if z.strip()}
    camaras = {cam: [f"{zona}-{i:02d}" for i in range(1, n + 1) if f"{zona}-{i:02d}" not in omitir] for zona, cam, n, _ in ZONAS if not solo or zona in solo}
    if not camaras:
        raise SystemExit(f"Ninguna isla coincide con --zonas {args.zonas!r}")

    http = requests.Session()
    http.headers["X-API-Key"] = clave_de_ingesta()
    sim = SimuladorIslas(camaras, perfil, args.hora_simulada, args.interval, colgantes_de_muestra(args.muestra), random.Random(args.seed))
    total = sum(len(v) for v in camaras.values())
    print(f"Simulando {total} cajones en {len(camaras)} islas ({len(omitir)} los vigila el modelo). 1 hora simulada = {args.hora_simulada:.0f} s. Ctrl+C para detener.")
    t0 = time.time()
    try:
        while True:
            for cam, items in sim.paso(time.time() - t0).items():
                try:
                    http.post(f"{args.api.rstrip('/')}/ingest/ocupacion", json={"camara": cam, "espacios": items}, timeout=5).raise_for_status()
                except requests.RequestException as e:
                    print(f"{cam}: no se pudo enviar ({e})")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulación detenida.")


if __name__ == "__main__":
    main()

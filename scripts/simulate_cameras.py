"""Simula las cámaras publicando ocupación a la API, para demostrar el sistema sin cámaras reales.

    python scripts/simulate_cameras.py --api http://localhost:8000 --interval 2

Usa INGEST_API_KEY del entorno o del .env de la raíz. Los autos entran y salen de forma aleatoria;
el 70 % de las entradas llevan el colgante de demostración IEST-004512 (el del usuario demo).
Ctrl+C para detener.
"""
import argparse
import os
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
from app.seed import ZONAS  # noqa: E402  (misma distribución de zonas y cámaras que la BD inicial)

COLGANTE_DEMO = "IEST-004512"


def clave_de_ingesta() -> str:
    if os.environ.get("INGEST_API_KEY"):
        return os.environ["INGEST_API_KEY"]
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("INGEST_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("Falta INGEST_API_KEY (variable de entorno o .env)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--interval", type=float, default=2.0, help="segundos entre actualizaciones")
    ap.add_argument("--ocupacion-inicial", type=float, default=0.5, help="fracción de cajones ocupados al empezar")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rnd = random.Random(args.seed)
    http = requests.Session()
    http.headers["X-API-Key"] = clave_de_ingesta()

    camaras = {cam: [f"{zona}-{i:02d}" for i in range(1, n + 1)] for zona, cam, n, _ in ZONAS}
    estado = {num: rnd.random() < args.ocupacion_inicial for nums in camaras.values() for num in nums}
    con_colgante: str | None = None  # cajón que tiene el colgante demo (solo puede estar en uno a la vez)
    primera = True

    print(f"Simulando {len(camaras)} cámaras contra {args.api}. Ctrl+C para detener.")
    try:
        while True:
            for cam, numeros in camaras.items():
                if primera:
                    cambios = numeros  # primer envío: estado completo
                else:
                    cambios = rnd.sample(numeros, k=rnd.randint(0, 2))
                    for n in cambios:
                        estado[n] = not estado[n]
                        if con_colgante == n and not estado[n]:
                            con_colgante = None  # el auto se fue: el colgante queda libre para otra entrada
                payload = []
                for n in cambios:
                    item = {"numero": n, "ocupado": estado[n], "confianza": round(rnd.uniform(0.6, 0.98), 2) if estado[n] else None}
                    if estado[n] and con_colgante is None and rnd.random() < 0.7:
                        item["colgante_codigo"], item["colgante_tipo"] = COLGANTE_DEMO, "estudiante"
                        con_colgante = n
                    payload.append(item)
                try:
                    r = http.post(f"{args.api.rstrip('/')}/ingest/ocupacion", json={"camara": cam, "espacios": payload}, timeout=5)
                    r.raise_for_status()
                except requests.RequestException as e:
                    print(f"{cam}: no se pudo enviar ({e})")
                    continue
                for n in cambios if not primera else []:
                    print(f"{cam} {n} -> {'OCUPADO' if estado[n] else 'libre'}")
            primera = False
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulación detenida.")


if __name__ == "__main__":
    main()

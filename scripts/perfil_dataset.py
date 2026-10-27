"""Resume el dataset de Kaggle "Smart Parking Management" en un perfil agregado para la simulación.

    python scripts/perfil_dataset.py --csv datasets/kaggle_smart_parking/IIoT_Smart_Parking_Management.csv

Escribe demo/perfil_ocupacion.json con proporciones (no copia los datos): ocupación media, distribución de la duración
de la estancia y mezcla de tipos de usuario y de vehículo. Lo usa scripts/simulate_cameras.py.

OJO: el dataset es sintético (1000 filas generadas, con sensores sin relación con la ocupación y fechas/horas
incoherentes; ver docs/DATASET_KAGGLE.md). Sirve para darle forma realista a la demostración, no como dato real.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def proporciones(valores) -> dict[str, float]:
    c = Counter(valores)
    total = sum(c.values())
    return {str(k): round(v / total, 4) for k, v in sorted(c.items(), key=lambda kv: -kv[1])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--salida", type=Path, default=ROOT / "demo" / "perfil_ocupacion.json")
    args = ap.parse_args()

    with args.csv.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    ocupados = sum(r["Occupancy_Status"] == "Occupied" for r in filas)
    duraciones = proporciones(int(r["Parking_Duration"]) for r in filas)
    perfil = {
        "fuente": "Kaggle: datasetengineer/smart-parking-management-dataset (sintético, 1000 filas)",
        "registros": len(filas),
        "ocupacion_media": round(ocupados / len(filas), 3),
        "duracion_horas": {k: v for k, v in sorted(duraciones.items(), key=lambda kv: int(kv[0]))},  # P(estancia = k horas)
        "duracion_media_horas": round(sum(int(k) * v for k, v in duraciones.items()), 2),
        "tipo_usuario": proporciones(r["User_Type"] for r in filas),
        "tipo_vehiculo": proporciones(r["Vehicle_Type"] for r in filas),
        "tamano_cajon": proporciones(r["Spot_Size"] for r in filas),
        "cajones_reservados": round(sum(r["Reserved_Status"] == "1" for r in filas) / len(filas), 3),
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(perfil, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Perfil escrito en {args.salida}")
    print(json.dumps({k: perfil[k] for k in ("ocupacion_media", "duracion_media_horas", "tipo_usuario", "tipo_vehiculo")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

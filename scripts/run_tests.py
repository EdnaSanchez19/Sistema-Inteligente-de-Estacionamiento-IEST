"""Ejecuta todas las pruebas del proyecto y la verificación de tipos de la app.

Uso (desde la raíz del repo):  python scripts/run_tests.py [--sin-app]
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(nombre: str, cmd: list[str], cwd: Path) -> bool:
    print(f"\n=== {nombre} ===", flush=True)
    return subprocess.run(cmd, cwd=cwd).returncode == 0


def main() -> int:
    py = sys.executable
    pasos = [
        ("API y base de datos", [py, "-m", "pytest", "tests", "-q"], ROOT / "api"),
        ("Servidor de visión (lógica)", [py, "-m", "pytest", "vision/tests", "-q"], ROOT),
        ("End-to-end (API real + visión + contrato con la app)", [py, "-m", "pytest", "tests/e2e", "-q"], ROOT),
    ]
    if "--sin-app" not in sys.argv:
        npm = shutil.which("npm")
        if npm and (ROOT / "mobile" / "node_modules").exists():
            pasos.append(("App móvil (TypeScript)", [npm, "run", "typecheck", "--silent"], ROOT / "mobile"))
        else:
            print("Se omite la app: falta npm o 'npm install' en mobile/")
    resultados = [(n, run(n, c, d)) for n, c, d in pasos]
    print("\n=== Resumen ===")
    for nombre, ok in resultados:
        print(f"{'OK     ' if ok else 'FALLÓ  '} {nombre}")
    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())

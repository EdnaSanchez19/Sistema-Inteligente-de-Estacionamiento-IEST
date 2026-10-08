"""Verifica que el entorno de desarrollo tenga lo necesario (tarea 3.2).

Uso: python scripts/check_env.py
"""
import importlib
import shutil
import subprocess
import sys

OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FALLA]"
failures = 0


def report(status: str, msg: str) -> None:
    global failures
    if status == FAIL:
        failures += 1
    print(f"{status} {msg}")


def check_module(name: str, required: bool = True, attr: str = "__version__") -> object | None:
    try:
        mod = importlib.import_module(name)
    except ImportError:
        report(FAIL if required else WARN, f"{name} no está instalado")
        return None
    report(OK, f"{name} {getattr(mod, attr, '')}".strip())
    return mod


def check_tool(cmd: str, required: bool) -> None:
    path = shutil.which(cmd)
    if not path:
        report(FAIL if required else WARN, f"'{cmd}' no se encontró en el PATH")
        return
    out = subprocess.run([cmd, "--version"], capture_output=True, text=True).stdout.strip().splitlines()
    report(OK, f"{cmd}: {out[0] if out else path}")


def main() -> int:
    v = sys.version_info
    report(OK if v >= (3, 10) else FAIL, f"Python {v.major}.{v.minor}.{v.micro} (se requiere >= 3.10)")

    print("\n-- Visión --")
    check_module("numpy")
    cv2 = check_module("cv2")
    if cv2 is not None and "FFMPEG:                      YES" not in cv2.getBuildInformation():
        report(WARN, "OpenCV sin FFMPEG: la captura RTSP podría no funcionar")
    check_module("ultralytics")
    torch = check_module("torch")
    if torch is not None:
        cuda = torch.cuda.is_available()
        report(OK if cuda else WARN, f"CUDA {'disponible: ' + torch.cuda.get_device_name(0) if cuda else 'no disponible (se usará CPU)'}")
    check_module("easyocr", required=False)

    print("\n-- API --")
    for mod in ("fastapi", "sqlalchemy", "pydantic_settings", "jwt", "psycopg"):
        check_module(mod, required=False)

    print("\n-- Herramientas --")
    check_tool("git", True)
    check_tool("docker", False)
    check_tool("node", False)

    print()
    if failures:
        print(f"{failures} problema(s) crítico(s). Revisa el README (Puesta en marcha).")
    else:
        print("Entorno listo.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

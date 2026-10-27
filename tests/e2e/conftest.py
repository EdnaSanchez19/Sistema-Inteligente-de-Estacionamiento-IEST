"""Fixtures de las pruebas de integración end-to-end (tarea 3.6).

Levanta la API real (uvicorn) en un proceso aparte con una base SQLite temporal y datos de
prueba. Las pruebas conectan el servidor de visión a ella por HTTP, igual que en producción.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision"))

INGEST_KEY = "clave-ingesta-e2e"
ADMIN = ("admin@iest.edu.mx", "admin-e2e-pass-1")
DEMO = ("demo@iest.edu.mx", "demo-e2e-pass-1")


def wait_until(cond, timeout: float = 15.0, step: float = 0.1):
    """Espera a que cond() devuelva algo verdadero; lo devuelve o falla con TimeoutError."""
    end = time.time() + timeout
    while time.time() < end:
        value = cond()
        if value:
            return value
        time.sleep(step)
    raise TimeoutError("La condición no se cumplió a tiempo")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, base: str):
        self.base = base
        self.key = {"X-API-Key": INGEST_KEY}

    def _login(self, creds) -> dict:
        r = requests.post(f"{self.base}/auth/login", data={"username": creds[0], "password": creds[1]}, timeout=10)
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @property
    def admin(self) -> dict:
        return self._login(ADMIN)

    @property
    def demo(self) -> dict:
        return self._login(DEMO)

    def get(self, path: str, headers: dict):
        r = requests.get(f"{self.base}{path}", headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, headers: dict, json: dict):
        r = requests.post(f"{self.base}{path}", headers=headers, json=json, timeout=10)
        r.raise_for_status()
        return r.json()

    def estados(self, headers: dict) -> dict[str, str]:
        return {e["numero"]: e["estado"] for e in self.get("/espacios", headers)}

    def monitoreados(self, headers: dict) -> set[str]:
        """Cajones que una cámara ya observó (su estado inicial quedó fijado)."""
        return {e["numero"] for e in self.get("/espacios", headers) if e["monitoreado"]}


@pytest.fixture(scope="session")
def api(tmp_path_factory) -> Api:
    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db.as_posix()}",
        "JWT_SECRET": "secreto-e2e-con-longitud-suficiente-123",
        "INGEST_API_KEY": INGEST_KEY,
        "SEED_ADMIN_PASSWORD": ADMIN[1],
        "SEED_DEMO_PASSWORD": DEMO[1],
        "PYTHONIOENCODING": "utf-8",
    }
    subprocess.run([sys.executable, "-m", "app.seed", "--demo"], cwd=ROOT / "api", env=env, check=True, capture_output=True)
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT / "api",
        env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_until(lambda: _up(base), timeout=30)
        yield Api(base)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _up(base: str) -> bool:
    try:
        return requests.get(f"{base}/health", timeout=1).ok
    except requests.RequestException:
        return False

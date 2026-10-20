KEY = {"X-API-Key": "clave-ingesta-pruebas"}


def login(client, correo, password):
    r = client.post("/auth/login", data={"username": correo, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None


ADMIN = ("admin@iest.edu.mx", "admin-pass-123")
DEMO = ("demo@iest.edu.mx", "demo-pass-123")

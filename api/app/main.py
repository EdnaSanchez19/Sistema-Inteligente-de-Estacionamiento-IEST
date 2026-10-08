from fastapi import FastAPI

app = FastAPI(title="Estacionamiento IEST API", version="0.1.0")


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"status": "ok"}

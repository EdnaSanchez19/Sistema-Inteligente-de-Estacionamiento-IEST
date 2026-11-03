FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
EXPOSE 8000
# Crea las tablas y carga los cajones, las cámaras y el administrador (es idempotente) y luego arranca la API.
# /srv/camaras lo monta docker-compose: el seed deja "sin monitoreo" los cajones que esa configuración no define.
CMD ["sh", "-c", "python -m app.seed --vigilados /srv/camaras/camaras.json && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Servidor de visión con GPU NVIDIA (necesita el NVIDIA Container Toolkit o Docker Desktop con WSL2).
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/vision
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY parking_vision ./parking_vision
EXPOSE 8100
# Los modelos (models/), la configuración de las cámaras (../camaras) y los videos (../datasets/reales) se montan desde fuera.
CMD ["python", "-m", "parking_vision.servidor", "--config", "../camaras/camaras.json", "--host", "0.0.0.0", "--puerto", "8100"]

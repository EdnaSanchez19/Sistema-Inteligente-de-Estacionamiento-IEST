# Servidor de procesamiento de imagen (tarea 3.4)

```
CameraStream (RTSP) ─▶ VehicleDetector (YOLO) ─▶ compute_occupancy (ROI) ─▶ OccupancyTracker ─▶ ApiPublisher ─▶ API
                                      └─▶ PendantReader (YOLO propio + OCR, opcional)
```

| Módulo | Qué hace |
|---|---|
| `capture.py` | Lee RTSP/video/imagen en un hilo, se queda con el último fotograma y reconecta solo |
| `detector.py` | YOLO (`yolov8n.pt` por defecto) filtrado a auto, moto, bus y camión |
| `occupancy.py` | Compara vehículos con los polígonos de los cajones y aplica antirrebote temporal |
| `pendant.py` | Detecta el colgante, clasifica su tipo y lee su ID con OCR (opcional) |
| `publisher.py` | Envía cambios, estado de cámara y latidos a la API; un fallo de red no detiene nada |
| `run.py` | Un hilo por cámara; procesa un fotograma cada `interval_s`, no cada cuadro |

## Cómo decide si un cajón está ocupado

1. YOLO detecta vehículos con confianza ≥ `conf`.
2. De cada recuadro se toma la parte inferior (`footprint`, 60 %), que aproxima dónde toca el suelo.
3. Cada vehículo se asigna **a un solo cajón**: aquel con el que su huella se solapa más. Así la
   perspectiva o un auto grande no marcan también los cajones vecinos.
4. El cajón queda ocupado si la huella cubre ≥ `occupied_ratio` (30 %) de su área.
5. Un cajón cambia de estado solo tras `confirm_occupied` (2) o `confirm_free` (3) observaciones
   seguidas iguales, para evitar parpadeos (personas cruzando, autos en maniobra).

`conf`, `occupied_ratio` y `footprint` son valores iniciales: **hay que calibrarlos con las cámaras
reales** (tareas 4.3 y 4.4). Con el dataset PKLot se pueden comparar combinaciones con `evaluate_pklot`.

## Uso

```bash
cd vision
pip install -r requirements.txt
cp config/cameras.example.json config/cameras.json    # y pon las URL reales con ${VARIABLES}

# 1. Dibuja los cajones sobre un fotograma de la cámara (clic en 4 esquinas, Enter para cerrar)
python -m parking_vision.tools.define_spaces --camera CAM-01 --prefix A \
    --source "rtsp://${CAM01_USER}:${CAM01_PASS}@192.168.1.64:554/Streaming/Channels/101"

# 2. Prueba en un fotograma y revisa la imagen resultante en salida/
python -m parking_vision.run --once

# 3. Ejecuta sin enviar a la API, y luego en producción (requiere INGEST_API_KEY en .env)
python -m parking_vision.run --dry-run
python -m parking_vision.run
```

- Las credenciales RTSP van en variables de entorno (`.env`) y se referencian como `${VAR}`;
  nunca se escriben en el JSON.
- Si una cámara cambia de posición solo se vuelven a dibujar sus cajones; no se toca el código.
- La primera ejecución descarga `yolov8n.pt` automáticamente (Ultralytics).
- Un único modelo se comparte entre cámaras con un candado; con muchas cámaras conviene subir
  `interval_s`.

## Colgantes (clasificación + OCR)

Requiere un modelo YOLO propio entrenado con fotos de los colgantes del IEST (una clase por tipo).
Se activa poniendo su ruta en `pendant_model` del JSON. Sin ese modelo el sistema reporta
ocupación normalmente y los vehículos quedan como "sin colgante identificado". Para leer el ID
instala `easyocr` y ajusta `pendant_code_regex` al formato real de los códigos.

## Reentrenamiento

Con `"save_low_confidence": true` se guardan (máx. 500, una cada 30 s por cámara) los fotogramas
donde YOLO dudó, en `frames_baja_confianza/`, y la API registra un evento `error_deteccion`.
Está desactivado por defecto porque la arquitectura prevé no conservar imágenes; actívalo solo
durante la etapa de recolección de datos y bórralos después de etiquetar.

## Pruebas

```bash
python -m pytest vision/tests -q      # desde la raíz del repo
```

## Evaluación con PKLot (tarea 4.1)

```bash
python -m parking_vision.tools.evaluate_pklot --root /ruta/a/PKLot --limit 200
```

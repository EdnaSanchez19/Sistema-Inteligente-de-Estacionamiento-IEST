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

## Cómo decide si un cajón está libre, ocupado u obstruido

1. YOLO detecta vehículos con confianza ≥ `conf`.
2. De cada recuadro se toma la parte inferior (`footprint`, 60 %), que aproxima dónde toca el suelo.
3. Cada vehículo se asigna **a un solo cajón**: aquel con el que su huella se solapa más. Así la
   perspectiva o un auto grande no marcan también los cajones vecinos.
4. El cajón queda ocupado si la huella cubre ≥ `occupied_ratio` (30 %) de su área.
5. Un cajón cambia de estado solo tras `confirm_occupied` (2) o `confirm_free` (3) observaciones
   seguidas iguales, para evitar parpadeos (personas cruzando, autos en maniobra).
6. **Histéresis:** para *marcar* un cajón ocupado se exige `conf`, pero uno que ya estaba ocupado se conserva mientras haya
   una detección con al menos `conf_baja` (por defecto 0.6 x `conf`). Así un auto parcialmente tapado, que el modelo ve a
   ratos, no hace parpadear el cajón ni genera entradas y salidas falsas.
7. La **primera** observación de un cajón fija su estado inicial en la API: no es una entrada ni una salida.
8. **Obstruido** (amarillo): el cajón no tiene vehículo pero sí un objeto que no lo es. YOLO detecta, además de vehículos,
   las clases COCO persona, bicicleta, mochila, bolsa, maleta, paraguas, perro, gato, pelota, silla, sillón, banca y planta
   (`obstacle_classes`). Un objeto con confianza ≥ `conf_obstaculo` (0.40) obstruye el cajón donde apoya su base si al
   menos `obstaculo_ratio` (50 %) de ella cae dentro. **Un vehículo manda sobre cualquier objeto**: una persona junto a un
   auto no cambia un cajón ocupado. Para pasar a obstruido hacen falta `confirm_obstruido` (6) observaciones seguidas, de
   modo que alguien que solo cruza no cuenta, y *obstruido nunca es el estado inicial* (un peatón del primer fotograma no
   obstruye nada). `detectar_obstaculos: false` desactiva todo esto en una cámara.

**Límite conocido:** solo se reconocen las clases de arriba. Un cono, una caja, escombro o cualquier cosa que YOLO no tenga
como clase **no** se detecta, y el cajón sigue "libre" (se midió, ver `docs/SIMULACION.md`). Para esos casos haría falta un
modelo entrenado con objetos reales del estacionamiento, o comparar cada cajón contra su aspecto vacío; ambas cosas
necesitan grabaciones reales para afinarse.

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

## Cajones de una cámara fija

`python scripts/completar_cajones.py --camara CAM-02 --imagen revisar.jpg` agrega a una cámara los coches estacionados que
quedaron fuera de sus cajones (los numera a continuación; los anteriores no cambian) y, con `--region-marcas x1,y1,x2,y2`,
también los cajones vacíos pintados de una zona. Los cajones que existen en el sistema son los del estacionamiento real
(`api/app/seed.py`: 391); si un video de demostración dibuja más cajones que los reales de su isla, la API ignora los sobrantes.
Los cajones muy lejanos (rayas de pocos píxeles) no se vigilan: un auto ahí mide pocos píxeles y el modelo no lo distingue.

`python scripts/descubrir_cajones.py --video v.mp4` propone cajones a partir de dónde se estacionan los autos (solo donde
hubo un auto); `scripts/cajones_cam02.py` es el ejemplo de cómo se combinaron con los cajones vacíos marcados en el pavimento
para la cámara CAM-02. En producción los cajones se dibujan sobre las líneas con `parking_vision.tools.define_spaces`.
`parking_vision.demo_server` procesa videos como cámaras y emite el video anotado (ver `docs/EJECUCION.md`).

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

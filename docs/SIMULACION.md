# Simulación con video (sin acceso a las cámaras)

Como el IEST no dará acceso a las cámaras, la validación de las fases 4.1, 4.3 y 4.4 se hace con **video grabado**
tratado como si fuera una cámara. Esta guía explica cómo y qué se puede (y qué no) concluir.

## Qué se puede demostrar con simulación

| Se puede | No se puede |
|---|---|
| Precisión del detector y de las reglas de ocupación (con un video real etiquetado) | Que las cámaras del IEST soporten RTSP o tengan buen ángulo |
| Calibrar `conf`, `occupied_ratio` y `footprint` | Rendimiento con la iluminación y el clima **reales** del lugar |
| Sensibilidad a noche, lluvia, niebla, sol y ruido (aproximada, con filtros) | Latencia y ancho de banda de la red del IEST |
| Captura RTSP, caída y reconexión de una "cámara" | Comportamiento con los modelos de cámara del campus |
| La cadena completa: video → visión → API → app | Detección de colgantes (no hay modelo entrenado) |

Por eso el informe de 4.3 debe decir que el piloto fue **simulado con video** y quedar pendiente el piloto real.

## Herramientas

| Herramienta | Para qué |
|---|---|
| `parking_vision.tools.define_spaces` | Dibujar los cajones sobre un fotograma del video (`--source video.mp4`) |
| `parking_vision.tools.etiquetar` | Marcar a mano qué cajones están ocupados en fotogramas del video (la verdad) |
| `parking_vision.tools.procesar_video` | Procesa el video completo, genera video con cajones, línea de tiempo, eventos y métricas |
| `parking_vision.tools.condiciones` | Degrada el video: `noche`, `lluvia`, `niebla`, `sol`, `ruido` |
| `parking_vision.tools.comparar_condiciones` | Sin etiquetas: cuántos vehículos de la imagen original sigue encontrando el modelo en cada condición |
| `procesar_video --estabilizar` | Los cajones acompañan el movimiento de la cámara (dron, viento, vibración) |
| `scripts/simular_rtsp.py` | Publica el video por RTSP como una cámara IP, con caídas programables |
| `scripts/simulate_cameras.py` | Publica ocupación aleatoria directo a la API (para demostrar la app) |
| `scripts/crear_video_prueba.py` | Montaje sintético con verdad conocida, solo para probar las herramientas |

Todos se ejecutan desde `vision/` con `python -m parking_vision.tools.<nombre>`, salvo los `scripts/`.

## Receta con tu video real

**1. Conseguir el video.** Lo ideal: cámara fija, vista elevada parecida a la de una cámara de vigilancia (desde
un piso alto o una azotea), mínimo 1280×720, 10–20 minutos con entradas y salidas de vehículos. Puede ser una
grabación propia con el celular fijo en un tripié, o un video con licencia libre (Pexels, Mixkit, etc.: revisa la
licencia). Guárdalo en `datasets/` (carpeta ignorada por git): no subas videos al repositorio, sobre todo si se
ven placas o personas.

**2. Dibujar los cajones** sobre un fotograma:

```bash
cd vision
python -m parking_vision.tools.define_spaces --config config/cameras.json --camera CAM-01 --prefix A \
    --source ../datasets/estacionamiento.mp4
```

**3. Etiquetar la verdad** (30–50 fotogramas bastan; tarda unos 10 minutos):

```bash
python -m parking_vision.tools.etiquetar --config config/cameras.json --camera CAM-01 \
    --video ../datasets/estacionamiento.mp4 --cada 20 --salida ../datasets/etiquetas.csv
```

Clic en un cajón = alternar libre/ocupado, Enter = guardar y seguir. Etiqueta a ojo, sin ayuda del modelo.

**4. Medir:**

```bash
python -m parking_vision.tools.procesar_video --config config/cameras.json --camera CAM-01 \
    --video ../datasets/estacionamiento.mp4 --etiquetas ../datasets/etiquetas.csv \
    --salida ../salida/resultado.mp4 --csv ../salida/linea_de_tiempo.csv
```

Imprime exactitud, precisión, recall, matriz de confusión y los eventos de entrada/salida. Revisa
`salida/resultado.mp4`: ahí se ven los errores concretos (cajones mal dibujados, sombras, autos grandes).

**5. Calibrar.** Prueba valores y quédate con los que mejor midan (sin sobreajustar: usa fotogramas distintos de
los que miraste para decidir):

```bash
python -m parking_vision.tools.procesar_video ... --ratio 0.25 --footprint 0.6 --conf 0.30
```

Cuando elijas, escribe los valores en `config/cameras.json`.

**6. Condiciones adversas** (tarea 4.4):

```bash
python -m parking_vision.tools.condiciones --video ../datasets/estacionamiento.mp4 --todas --carpeta ../salida/condiciones
# y mide cada versión con el comando del paso 4 (--video ../salida/condiciones/estacionamiento_noche.mp4, etc.)
```

Los filtros solo aproximan la realidad. Si el sistema falla mucho de noche en la simulación, hay que recolectar
video nocturno real para reentrenar.

**7. Cámara RTSP simulada.** Requiere `ffmpeg` y [mediamtx](https://github.com/bluenviron/mediamtx/releases)
(un ejecutable que se guarda en `herramientas_externas/mediamtx/`, ignorado por git):

```bash
python scripts/simular_rtsp.py --video datasets/estacionamiento.mp4 --caida-tras 60 --pausa 15
# en config/cameras.json: "source": "rtsp://127.0.0.1:8554/cam1"
```

**8. Cadena completa con la app:**

```bash
# terminal 1: API (ver README) · terminal 2: cámara simulada · terminal 3:
cd vision && python -m parking_vision.run --config config/cameras.json
# terminal 4: app con EXPO_PUBLIC_USE_MOCK=false
```

## Resultados con el montaje sintético

Video de 30 s armado con la foto de un autobús real (`scripts/crear_video_prueba.py`), 3 cajones, verdad exacta
cada segundo, YOLOv8n real. **Prueba de las herramientas, no medida de precisión**: es una sola foto sobre
asfalto liso, mucho más fácil que un estacionamiento real.

| Versión | Exactitud | Precisión | Recall | Entradas / salidas detectadas |
|---|---|---|---|---|
| Original | 0.944 | 0.927 | 0.950 | 2 / 2 |
| Noche | 0.856 | 0.886 | 0.775 | 3 / 3 (una de más: parpadeo) |
| Lluvia | 0.933 | 0.905 | 0.950 | 2 / 2 |
| Niebla | 0.933 | 0.905 | 0.950 | 2 / 2 |
| Sol de frente | 0.933 | 0.905 | 0.950 | 2 / 2 |
| Ruido y compresión | 0.933 | 0.905 | 0.950 | 2 / 2 |

Lo que sí muestra: las herramientas funcionan de punta a punta, y la noche es la condición que más degrada la
detección (recall 0.95 → 0.78). Los errores de la versión original son el retraso de 1–2 s por la confirmación de
cambios, no fallos del modelo. La cadena RTSP → visión → API también se probó (el video publicado por mediamtx, el
servidor de visión con YOLO y la API reflejando entradas y salidas), y la captura se reconecta sola tras una caída.

## Resultados con el video generado con IA (Gemini)

Video de 10 s, 1280×720, 24 fps: una toma **aérea que avanza** sobre un estacionamiento de centro comercial con
unos 80 autos. Está **generado con IA**, no es una grabación real, y eso importa: la escena cambia mientras la
cámara se mueve (a los 8 s ya no son los mismos autos en cada fila), no hay entradas ni salidas y casi todo está
ocupado. Sirve para probar el detector en una escena densa y de aspecto real, pero **no** para medir la
precisión que tendría el sistema con las cámaras del IEST.

**Detección.** YOLOv8n (imgsz 1280) encuentra entre 72 y 86 vehículos por fotograma, prácticamente todos los
visibles. Por el ángulo, los recuadros de autos vecinos se traslapan mucho; por eso cada vehículo se asigna a un
solo cajón y se usa la parte inferior del recuadro (`footprint`).

**Ocupación por cajón.** 8 cajones dibujados a ojo sobre el primer fotograma: 6 con auto y 2 sobre asfalto vacío
como control negativo; la verdad es constante (se etiquetó a ojo, no con el modelo).

| Tramo | Cajones fijos | Con `--estabilizar` |
|---|---|---|
| Primeros 2.5 s (toma casi estable) | **100 %** de exactitud (48 comparaciones), 0 eventos falsos | – |
| Primeros 5 s | – | 87.5 % (2 falsas salidas) |
| 10 s completos | – | 70.6 % (5 falsas salidas) |

Los cajones se "pierden" porque la proyección se deforma al cambiar la toma, no porque el modelo deje de ver los
autos (se comprobó en el video de salida). Con una **cámara fija real** este problema no existe. El estabilizador
queda disponible para cámaras que vibran un poco, no para una toma de dron.

**Condiciones adversas** (`comparar_condiciones`, 10 fotogramas, 792 vehículos de línea base; retención = fracción
de los vehículos del video original que el modelo sigue encontrando):

| Condición | Retención | Detecciones extra |
|---|---|---|
| Lluvia | 93.8 % | 4.0 % |
| Sol de frente | 84.3 % | 5.1 % |
| Ruido y compresión | 67.8 % | 3.9 % |
| Noche | 63.8 % | 4.0 % |
| Niebla | 54.7 % | 5.3 % |

La retención se mide contra lo que el modelo detecta en la imagen limpia, no contra una verdad etiquetada, y los
filtros solo aproximan el clima real. En esta escena muchos autos son pequeños y lejanos, que es lo primero que se
pierde; con cámaras más cercanas a los cajones debería ser mejor, pero eso hay que comprobarlo. Si la noche y la
niebla resultan críticas, habrá que probar un modelo mayor (yolov8s/m) y reentrenar con video nocturno real.

## Qué debería pedir el informe de validación (propuesta)

- Exactitud por cajón ≥ 90 % de día y ≥ 80 % de noche, con recall ≥ 85 % (que no se pierdan autos).
- Latencia de un cambio de estado ≤ 10 s.
- Cero eventos falsos por parpadeos en 10 minutos de video sin movimiento de vehículos.
- Reconexión automática de la cámara tras una caída, sin intervención.

Son propuestas para discutir con el equipo; el criterio final debe quedar en el acta de validación (5.1).

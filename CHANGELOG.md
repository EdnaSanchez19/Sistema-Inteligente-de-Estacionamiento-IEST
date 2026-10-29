# Cambios

## Sin versión — distribución real del estacionamiento y mapa (29/10/2026)

- **391 cajones, como el estacionamiento real.** 8 islas (A y G de 32, B a F de 36, H de 27) y 6 zonas del perímetro: lateral
  caseta (16), esquina motos (8), lateral biblioteca (42), lateral gimnasio (18), entrada lateral (4) y lateral callejón (32).
  Antes eran 8 islas de 40 más cajones extra que dibujaban los videos de demostración. Al iniciar se quitan los que no existen
  en la realidad (conservando sus eventos); el perímetro aparece "sin monitoreo" hasta que tenga cámaras. Se retiró
  `--cajones` del seed y de `sincronizar_cajones`: los videos de demostración ya no agregan cajones.
- **Mapa** en el panel: plano esquemático con las islas y el perímetro y cada cajón en su color en vivo (la posición de los
  bloques es aproximada, no está a escala). La app y el panel nombran "Isla A" o "Lateral caseta" según corresponda.
- **Botón de modo claro/oscuro** en el panel y en el inicio de sesión, y nuevo inicio de sesión con la foto del campus.

## Sin versión — tres estados por cajón y tiempo en el estado (27/10/2026)

- **Libre, ocupado u obstruido.** *Obstruido* (amarillo) es un cajón sin vehículo con un objeto que no lo es dentro (persona,
  maleta, bicicleta, mochila... las clases COCO de YOLO). Un vehículo manda sobre cualquier objeto; alguien que solo cruza no
  cuenta (hacen falta 6 observaciones seguidas) y *obstruido* nunca es el estado inicial. Nuevo estado en la API y la base de
  datos (con migración automática de SQLite y `db/migraciones/002_obstruido.sql` para PostgreSQL), eventos `obstruccion` y
  `obstruccion_retirada`, y amarillo en el panel y la app (el color de *reservado* pasa a azul).
- **Cuánto lleva cada cajón en su estado** (para un coche, cuánto lleva estacionado): `desde`, `duracion_s` y `desde_observado`
  (exacto si la cámara vio la llegada, "al menos" si no). Las salidas dicen cuánto estuvo; el panel lista los que llevan más
  tiempo (`GET /sistema/estancias`) y la app lo muestra al tocar un cajón.
- **Más cajones etiquetados.** Nuevo `scripts/completar_cajones.py` agrega los coches estacionados que habían quedado fuera de
  los cajones: CAM-02 pasa de 40 a 52 cajones y CAM-03 de 40 a 57. Las islas ya no están fijas en 40: los cajones que define la
  configuración se registran solos en la base de datos. Los cajones vacíos de zonas muy lejanas siguen sin vigilarse.
- **Validación con tres clases.** `procesar_video` usa ahora el mismo pipeline que el servidor (con histéresis) y calcula la
  matriz de confusión de libre/ocupado/obstruido; `etiquetar` marca los tres estados. Nueva prueba controlada
  `obstaculos_sinteticos` (los videos no tienen obstrucciones reales): una persona insertada se marca obstruido en 2.5 s, sin
  falsos amarillos en 15 250 observaciones; un cono o una caja **no** se detectan (límite documentado en `docs/SIMULACION.md`).
- Pruebas: 55 de API, 54 de visión y 21 end-to-end, más la verificación de tipos de la app.

## Sin versión — el sistema pasa a trabajar con datos reales (27/10/2026)

- **Cajones "sin monitoreo".** Un cajón que ninguna cámara ha observado ya no aparece como libre: la API expone
  `monitoreado` y la interfaz lo muestra rayado, con la cobertura por isla y en general. La primera observación de un cajón
  fija su estado inicial sin generar entradas ni salidas falsas, y los avisos "isla llena" exigen cobertura completa.
- **Panel rediseñado** (`/panel`): barra lateral con Resumen, Cámaras, Islas, Eventos, Administración y Sistema; detalle e
  historial de cada cajón; gráfica de ocupación en el tiempo; registro de usuarios, vehículos y colgantes. La app móvil
  muestra la misma cobertura.
- **CAM-02: cámara de seguridad real y fija** (isla B, 40 cajones, 23 ocupados y 17 vacíos al inicio) además de CAM-01
  (video generado con IA). Nuevo `scripts/descubrir_cajones.py` y `scripts/cajones_cam02.py`.
- **Histéresis** en la ocupación (`conf_baja`): un auto parcialmente tapado ya no hace parpadear el cajón.
- `scripts/iniciar_sistema.py` levanta todo con datos reales; la simulación pasa a ser opcional (`--con-simulacion`).
- Nuevos endpoints: `GET /espacios/{numero}`, `GET /sistema/historial`; migración automática de la columna `monitoreado`.
- Análisis del dataset de Kaggle (sintético, sin imágenes): `docs/DATASET_KAGGLE.md`.
- **CAM-03** (isla C, otra vista de la cámara de seguridad, 40 cajones) y **CAM-04** (isla D, estacionamiento techado, 8
  cajones, con un vehículo que cruza). `scripts/agregar_camara.py` agrega cualquier cámara fija: descubre los cajones con
  autos, arma los vacíos entre las rayas blancas y regenera la configuración.
- **Calentamiento:** tras arrancar o reiniciar un video, los cambios de estado se toman como estado inicial y no como
  entradas o salidas falsas (p. ej., un auto tapado por un vehículo que pasa).
- **Rendimiento:** el servidor de visión solo dibuja y comprime el video cuando alguien lo mira.

## Sin versión — panel de demostración (27/10/2026)

El estacionamiento pasa a **8 islas de 40 cajones** (320 en total) con una cámara por isla (`CAM-01` a `CAM-08`); antes eran
3 zonas de ejemplo. La app, el panel y los avisos hablan de "islas".

Panel web (`/panel`) rediseñado con los colores institucionales: video de cámara fija con el modelo YOLO detectando en
vivo, flujo del sistema con estado real, estado del modelo (latencia, FPS, vehículos), mapa de cajones con destellos
al cambiar, eventos, cámaras y avisos. Nuevo `scripts/iniciar_demo.py` (hoy `iniciar_sistema.py`) que lo levanta todo; `GET /sistema/estado` y
`POST /ingest/modelo` en la API; CORS configurable; la app móvil adopta los mismos colores. Corrige el paquete
`expo-asset` que faltaba en la app. El video es generado con IA y las zonas B y C son simuladas (ver `docs/EJECUCION.md`).

## Sin versión — banco de simulación con video (20/10/2026)

Como no habrá acceso a las cámaras del IEST, se agregó lo necesario para validar con video: procesamiento de
video con métricas (`procesar_video`), etiquetado manual (`etiquetar`), degradación por condiciones
(`condiciones`: noche, lluvia, niebla, sol, ruido), cámara RTSP simulada (`scripts/simular_rtsp.py`, con ffmpeg y
mediamtx), captura RTSP por TCP y pruebas automáticas (55 en total). Guía en [`docs/SIMULACION.md`](docs/SIMULACION.md).
Se probó con un video generado con IA (toma aérea de ~80 autos): detección sólida y mediciones de sensibilidad a
noche y niebla en `docs/SIMULACION.md`. Sigue faltando un video de **cámara fija real** para medir la precisión.

## 1.0.0 — 20/10/2026 · Versión funcional (hito 3.7)

Primera versión completa de punta a punta, lista para entrar a las pruebas (fase 4).

### Qué incluye
- **Detección de ocupación** por cámara con YOLOv8 y ROI de cada cajón, con antirrebote temporal y
  monitoreo de la señal RTSP (reconexión automática y alerta de desconexión).
- **API** con login JWT, roles (usuario / administrador), consulta de espacios, vehículos y avisos,
  administración de usuarios, vehículos, colgantes y asignación de cajones, corrección manual de estados,
  historial de eventos, avisos automáticos de zona casi llena/llena y vigilancia de cámaras sin señal.
- **Base de datos** relacional (PostgreSQL; SQLite para pruebas) con la cadena usuario → vehículo →
  colgante → espacio y el historial de eventos.
- **App móvil** (React Native): inicio, mapa por zona, avisos, mi cuenta y vista de administración; sesión
  guardada de forma segura y actualización automática.
- **Herramientas:** dibujo de cajones sobre el video, simulador de cámaras para demostraciones, evaluación con
  PKLot y `scripts/run_tests.py`.
- **Pruebas:** 46 automáticas (22 API, 8 visión, 16 end-to-end) y verificación de tipos de la app.

### Límites conocidos (por hacer en las fases 4 y 5)
- No se ha probado con las **cámaras reales** del IEST ni con video de un estacionamiento (4.3).
- Los umbrales de detección (`conf`, `occupied_ratio`, `footprint`) están **sin calibrar**; no hay métricas de
  precisión todavía (4.1 y 4.4).
- **Colgantes:** falta entrenar un modelo con los colgantes reales del IEST; hasta entonces los vehículos se
  registran como "sin colgante identificado". El OCR requiere instalar `easyocr` y ajustar el formato del código.
- La app no se ha ejecutado en un teléfono (compila y su contrato con la API está verificado).
- No se ha corrido contra un servidor **PostgreSQL** real ni desplegado en la nube.
- La app no tiene aún pantallas para que el administrador registre usuarios, vehículos y colgantes (la API sí;
  se usa desde `/docs`). Los colores son provisionales hasta tener los institucionales.
- Las migraciones de base de datos no están automatizadas (se crean las tablas al iniciar).

## 0.x — 3.1 a 3.4
- 3.1 App móvil · 3.2 Entorno · 3.3 Base de datos · 3.4 Detección, colgantes y API.

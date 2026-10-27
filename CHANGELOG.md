# Cambios

## Sin versión — panel de demostración (27/10/2026)

El estacionamiento pasa a **8 islas de 40 cajones** (320 en total) con una cámara por isla (`CAM-01` a `CAM-08`); antes eran
3 zonas de ejemplo. La app, el panel y los avisos hablan de "islas".

Panel web (`/panel`) rediseñado con los colores institucionales: video de cámara fija con el modelo YOLO detectando en
vivo, flujo del sistema con estado real, estado del modelo (latencia, FPS, vehículos), mapa de cajones con destellos
al cambiar, eventos, cámaras y avisos. Nuevo `scripts/iniciar_demo.py` que lo levanta todo; `GET /sistema/estado` y
`POST /ingest/modelo` en la API; CORS configurable; la app móvil adopta los mismos colores. Corrige el paquete
`expo-asset` que faltaba en la app. El video es generado con IA y las zonas B y C son simuladas (ver `docs/DEMO.md`).

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

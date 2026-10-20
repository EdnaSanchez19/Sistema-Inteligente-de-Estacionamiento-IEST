# Pruebas de integración end-to-end (tarea 3.6)

Fecha de la corrida: 20/10/2026 · Entorno: Windows 11, Python 3.12, GPU NVIDIA RTX 4050 Laptop.

```bash
python scripts/run_tests.py        # todo: API, visión, e2e y tipos de la app
python -m pytest tests/e2e -q      # solo las end-to-end
```

## Resultado

| Suite | Pruebas | Resultado |
|---|---|---|
| API y base de datos (`api/tests`) | 22 | Todas pasan |
| Servidor de visión, lógica y herramientas de simulación (`vision/tests`) | 12 | Todas pasan |
| End-to-end (`tests/e2e`) | 19 | Todas pasan |
| App móvil: `tsc --noEmit` | – | Sin errores |

## Qué cubren las end-to-end

Se levanta la **API real** (uvicorn) con una base temporal y se conecta a ella el **servidor de visión**
por HTTP, igual que en producción. La cámara es una imagen fija.

| Escenario | Qué verifica |
|---|---|
| Entrada y salida con colgante | Un auto entra al cajón A-02: la API lo marca ocupado y solo ese cajón; el evento de entrada incluye el cajón y el código del colgante; al irse queda libre y se registra la salida |
| Parpadeos | Un vehículo visible en un solo fotograma no cambia el estado ni genera eventos |
| Cámara sin señal | Una cámara que pierde el video queda "desconectada" y genera el evento para el administrador |
| Zona llena | Al ocuparse todos los cajones de la zona C, todos los usuarios reciben el aviso "Zona C llena" |
| **Modelo YOLO real** | Con una foto de un autobús: el modelo lo detecta (86 % de confianza, 178 ms en GPU), el cajón que lo cubre queda ocupado y uno vacío queda libre. Se omite si falta `vision/models/yolov8n.pt` o la foto |
| Cámara RTSP simulada | Con ffmpeg + mediamtx se publica un video por RTSP; la captura lo recibe, detecta la caída de la "cámara" y se reconecta sola al volver. Se omite si falta ffmpeg o mediamtx |
| Banco de simulación con video | Un video con verdad conocida se procesa con el modelo real y se miden las métricas; la versión nocturna simulada no mejora el resultado. Ver [`SIMULACION.md`](SIMULACION.md) |
| Contrato app ↔ API | Los campos de `mobile/src/types.ts` (usuario, espacio, vehículo con colgante, aviso, evento, cámara) existen en las respuestas de la API, y los valores de los enums coinciden |

Además, las pruebas de la API cubren: roles (solo admin ve eventos y cámaras), alta de usuarios, vehículos y
colgantes, desactivar usuarios, asignar espacios, corrección manual, avisos automáticos, vigilancia de cámaras sin
señal y secretos sin configurar.

## Lo que estas pruebas NO demuestran

- **Cámaras reales.** No habrá acceso a las cámaras del IEST: la validación se hace con video grabado y una cámara
  RTSP simulada (ver [`SIMULACION.md`](SIMULACION.md)). Falta correrla con un video real de estacionamiento.
- **Precisión del modelo.** Se probó que el pipeline funciona con el modelo real, no qué tan bien detecta. Para eso
  se necesita un dataset etiquetado (4.1): `evaluate_pklot` o fotos propias. Los umbrales siguen sin calibrar.
- **Colgantes.** No existe aún un modelo entrenado con los colgantes del IEST; las pruebas usan un lector simulado.
- **App en un teléfono.** Se verificó que compila (TypeScript) y que el contrato con la API coincide, pero no se
  ejecutó en un dispositivo o emulador.
- **PostgreSQL.** Las pruebas usan SQLite; el esquema de PostgreSQL se genera desde los mismos modelos pero no se
  ejecutó contra un servidor Postgres.

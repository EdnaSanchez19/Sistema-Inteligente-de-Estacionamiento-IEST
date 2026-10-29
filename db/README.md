# Base de datos (tarea 3.3)

PostgreSQL 16 (el mismo modelo funciona en SQLite para pruebas). La fuente de verdad es
[`api/app/models.py`](../api/app/models.py); [`schema.sql`](schema.sql) se genera con
`python scripts/export_schema.py`.

```mermaid
erDiagram
    USUARIOS ||--o{ VEHICULOS : tiene
    VEHICULOS ||--o| COLGANTES : "lleva (1 a 1)"
    USUARIOS ||--o{ ESPACIOS : "asignado a"
    COLGANTES ||--o| ESPACIOS : "ocupa ahora"
    ZONAS ||--o{ ESPACIOS : contiene
    ZONAS ||--o{ CAMARAS : cubre
    CAMARAS ||--o{ ESPACIOS : vigila
    ESPACIOS ||--o{ EVENTOS : genera
    CAMARAS ||--o{ EVENTOS : genera
    COLGANTES ||--o{ EVENTOS : "se asocia a"
    USUARIOS ||--o{ NOTIFICACIONES : recibe
```

| Tabla | Para qué sirve |
|---|---|
| `usuarios` | Estudiantes, docentes, directivos, administrativos, externos y admins. Contraseña solo como hash scrypt |
| `vehiculos` | Vehículos de cada usuario (la placa es opcional) |
| `colgantes` | Código leído por OCR + tipo; un colgante por vehículo |
| `zonas` / `camaras` | Zonas del estacionamiento y cámara RTSP que las cubre (estado y última señal) |
| `espacios` | Cajón: número, zona, tipo, estado actual, `monitoreado` (una cámara ya lo observó; si no, su "libre" es solo el valor inicial), `estado_desde` / `inicio_observado` (desde cuándo está así y si la cámara vio el cambio), `objeto` (qué lo obstruye), asignado y colgante que lo ocupa. Estados: libre, ocupado, **obstruido** (un objeto que no es vehículo), reservado y fuera de servicio |
| `eventos` | Historial de auditoría: entradas, salidas (con cuánto estuvo), obstrucciones y su retiro, cambios de ocupación, errores y cámaras caídas |
| `notificaciones` | Avisos para la app (`usuario_id` nulo = para todos) |

## Decisiones

- **Zona = isla o zona del perímetro.** El estacionamiento real tiene **391 cajones**: 8 islas con una cámara cada una
  (A y G: 32; B a F: 36, que son 32 más 2 por costado; H: 27 = 271) y 6 zonas del perímetro sin cámara todavía
  (lateral caseta 16, esquina motos 8, lateral biblioteca 42, lateral gimnasio 18, entrada lateral 4, lateral callejón 32 = 120).
  En el modelo de datos la tabla se llama `zonas`. Una isla se llama con su letra ("A", cajones `A-01`...) y se muestra como
  "Isla A"; las del perímetro por su nombre, con prefijo en el número (`CAS-01`, `MOT-01`, `BIB-01`, `GIM-01`, `ENT-01`, `CAL-01`).
  La distribución vive en `api/app/seed.py`; al iniciar se crean los cajones que falten y se quitan los que no existen en la
  realidad (sus eventos se conservan). Los cajones sin cámara aparecen "sin monitoreo".
- **Colgante vs. placa:** el cronograma habla de placas, la arquitectura de colgantes. El modelo usa el
  colgante como identificador principal y deja la placa como dato opcional del vehículo.
- Las URL RTSP (con usuario y contraseña) **no** se guardan aquí, solo en la config del servidor de visión.
- No se almacenan imágenes en la BD.
- Enums guardados como texto con `CHECK`, para poder migrar de motor sin sorpresas.

## Cargar datos iniciales

```bash
cd api
SEED_ADMIN_PASSWORD='una-clave-segura' python -m app.seed --demo
```

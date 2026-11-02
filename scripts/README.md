# Scripts

Lo que se usa a diario está en esta carpeta; lo demás, agrupado por tema.

| Script | Para qué |
|---|---|
| `iniciar_sistema.py` | Arranca API, visión y panel (`python scripts/iniciar_sistema.py`) |
| `servicio.ps1` / `servicio.bat` | Deja el sistema corriendo en segundo plano en Windows (`instalar`, `estado`, `detener`, `reiniciar`, `quitar`) |
| `run_tests.py` | Corre todas las pruebas |
| `check_env.py` | Revisa que el entorno esté completo |
| `export_schema.py` | Regenera `db/schema.sql` desde los modelos |

| Carpeta | Contenido |
|---|---|
| `etiquetado/` | Etiquetar coches para ajustar el modelo: `preparar_etiquetado.py` y `etiquetar_coches.py` (ver `docs/ETIQUETADO.md`) |
| `cajones_reales/` | Cámaras reales del IEST: `crear_config_real.py` arma `camaras/camaras.json` a partir de los polígonos de `camaras/cajones/`; `islas_cam02.py`, `islas_diagonales.py` y `cajon_por_coche.py` son las herramientas con las que se dibujaron |
| `simulacion/` | Datos inventados y videos de prueba: `simulate_cameras.py`, `simular_rtsp.py`, `crear_video_prueba.py`, `perfil_dataset.py` (ver `docs/SIMULACION.md`) |

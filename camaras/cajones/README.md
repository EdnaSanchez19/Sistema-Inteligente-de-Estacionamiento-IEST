# Cajones de las cámaras reales

Polígonos de los cajones dibujados sobre los videos reales (en píxeles del video). `scripts/cajones_reales/crear_config_real.py` los junta
en `camaras/camaras.json`, que es lo que lee el servidor de visión.

| Archivo | Qué es |
|---|---|
| `biblioteca_esquina.json` | Lateral de la biblioteca, tramo junto a las motos (`BIB-19` a `BIB-28`) |
| `isla1_c_cajones.json`, `isla1_d_cajones.json` | Fila 1 (isla A), filas c y d (`A-09` a `A-16` y `A-26` a `A-32`) |
| `motos_cajones.json` | Esquina de motos (`MOT-01` a `MOT-08`) |
| `por_coche_isla2.json` | Fila 2 (isla B): un cajón por cada coche visible |
| `isla_E_cajones.json`, `isla_F_cajones.json`, `isla_G_cajones.json`, `extremos_cam02.json` | Filas 5, 6 y 7 de la cámara general, y los cajones de los extremos |
| `biblioteca_cajones.json` | Lateral de la biblioteca (`BIB-01` a `BIB-18`) |
| `propuesta_cam_a.json`, `propuesta_cam_b.json` | Cajones provisionales sacados de los coches estacionados (la fila 4 sale de aquí) |

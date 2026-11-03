# Cambios

## Sin versión — cámaras reales del IEST (02/11/2026)

- **Fila 2 (CAM-01): 21 cajones** (`B-01` a `B-21`): se agregaron 4 pickups blancas del fondo de la isla que la auditoría de cobertura encontró fuera de
  todo cajón. Auditoría: 45 coches estables en CAM-01 y 70 en CAM-02; quedan fuera de cajón los de la zona de la caseta, el SUV plateado del
  extremo de la fila 1, dos coches del fondo de la fila 7 y los coches muy chicos del fondo derecho de CAM-02.
- **Se retira el modo demostración.** Fuera: los videos de demostración y su configuración (`cameras_demo.json`, `cajones_cam0N.json`), las
  herramientas para dibujar cajones sobre ellos (`scripts/cajones/`, `preparar_demo.py`) y sus pruebas. `iniciar_sistema.py` ya no tiene
  alternativa: sin los videos reales de `datasets/reales/` avisa cuáles faltan. La carpeta `demo/` pasa a `camaras/` (`camaras.json` y los
  polígonos en `camaras/cajones/`), `perfil_ocupacion.json` a `scripts/simulacion/`, y `parking_vision.demo_server` se llama ahora
  `parking_vision.servidor`. El simulador de datos inventados (`--con-simulacion`) se conserva.
- **Proyecto reordenado.** `scripts/` queda con lo de uso diario y tres subcarpetas (`etiquetado/`, `cajones_reales/`, `cajones/`, `simulacion/`; ver
  `scripts/README.md`); los polígonos de los cajones reales pasan a `demo/cajones_reales/`; las exportaciones de diseño que estaban sueltas en la
  raíz (`index.tsx`, `tailwind.*`, `tokens/`) pasan a `docs/diseno/`; el README principal trae el mapa de carpetas. Se retiró lo que no se
  versionaba y se podía regenerar (`salida/`, videos y datos de la época de demostración en `datasets/`, parches de una sola vez, imágenes de trabajo).
- **Lateral de la biblioteca reajustada (18 cajones, `BIB-01` a `BIB-18`)**: los bordes de los cajones se anclaron a los coches (los míos salían
  corridos ~40 px); `BIB-19` a `BIB-42` quedan sin monitoreo. Además, `obstaculo_grande` (CAM-02): un "objeto" que cubre al menos 40 % de un cajón se
  toma por un vehículo que el modelo no reconoció (ocupado, no obstruido). Un sedán oscuro visto desde arriba salía como "maleta" (obstruido, amarillo).
- **Etiquetado**: los 100 fotogramas se vuelven a pre-marcar con los dos modelos combinados (de 50 a 82 cajas por fotograma en las cámaras de cajones).
- **Lateral de la biblioteca (CAM-02): 20 cajones** (`BIB-01` a `BIB-20`, de izquierda a derecha; reajustada abajo a 18) a lo largo del bordillo de abajo, perpendiculares
  al bordillo y con los huecos vacíos incluidos; el ancho de cada cajón sale de los coches (110 px al centro, menos a los lados). Los otros 22
  (`BIB-21` a `BIB-42`) no se ven en esta cámara y quedan sin monitoreo. El sedán oscuro (`BIB-09`) no lo detecta ningún modelo.
- **Detector combinado** (`model_extra`): CAM-01 y CAM-02 corren YOLOv8n y YOLOv8s sobre el mismo fotograma y se queda lo que detecta cualquiera. Cada uno
  falla con coches distintos: v8s ve los SUV vistos desde arriba (0.8 de confianza contra 0.05) y v8n el sedán blanco (0.53 contra 0.24). La señal de
  detalle (bordes) que sirvió para las motos no sirve en esta hilera: su asfalto agrietado da hasta 22 % de bordes aun vacío.
- **Motos detectadas por detalle** (`detalle_min` por cajón): YOLOv8n y v8s casi no ven las motos del video (confianza de 0.05 a 0.4). Los cajones con
  `detalle_min` se marcan ocupados si el modelo no vio nada pero hay más de ese % de bordes dentro (el asfalto liso da 0 a 3 %, una moto de 5 % para
  arriba). En 16 fotogramas del video, `MOT-02`, `03`, `04`, `05` y `07` salen ocupados siempre y `MOT-01`, `06` y `08` nunca. Límite: una persona o
  un objeto grande dentro del cajón también lo marcaría ocupado. `MOT-08` se movió sobre el asfalto (pisaba la banqueta).
- **Isla 2 de CAM-01**: un cajón por cada coche visible (17, `B-01` a `B-17`) en lugar de los 16 provisionales. Sin cajones vacíos.
- **CAM-01: esquina de motos (8 cajones) y fila d de la isla 1.** `MOT-01` a `MOT-08`, a lo largo del bordillo junto a la barda y, el último,
  tras la esquina; las 5 motos del fotograma de prueba caen cada una en su cajón. La fila d (a la izquierda del camellón, `A-17` a `A-32`,
  de lejos a cerca) se dibujó con perspectiva y entran los 7 más cercanos (`A-26` a `A-32`); el resto queda fuera del encuadre. "Esquina
  motos" pasa a verse en la cámara "Fila 1 y 2". La isla 2 (`B`) sigue con cajones provisionales de los coches estacionados.
- **Cajones de los extremos** de las islas 5 y 6 de CAM-02 (`E-33`, `E-34`, `F-33`, `F-34`): son dos cajones en paralelo al bordillo de
  remate del extremo cercano, uno junto al otro (en la isla 5 son el coche azul claro y la camioneta naranja; en la 6, la franja de
  asfalto libre). Los dos del extremo lejano (`35` y `36`) no se ven marcados en la imagen y quedan sin dibujar. La fila derecha de la
  isla 5 se acortó hasta el remate: antes invadía el cajón del extremo.
- **CAM-02: filas 5, 6 y 7 con cajones completos** (las tres islas de la izquierda y el centro de la imagen). Cada isla tiene un camellón de
  árboles y dos filas de cajones, a cada lado; se dibujaron con perspectiva a lo largo de los bordillos amarillos, vacíos incluidos
  (`E-01` a `E-31`, `F-01` a `F-20` y `G-01` a `G-31`, la fila izquierda primero y luego la derecha, de lejos a cerca). La fila 5 va en
  diagonal (`islas_diagonales.py` generaliza la herramienta a filas en cualquier dirección) y sale con 15 y 16 por fila; la 7, con 15 y 16;
  la 6, con 10 y 10 (no llega a los 36 que le corresponden: queda por aclarar). Fotograma de prueba: la 6 acierta sus 4 coches y la 7, 5
  de 7. La fila 4 (la de más a la derecha, con coches muy chicos y tapados por árboles) sigue con cajones provisionales de los coches
  estacionados. La confianza para ocupar un cajón en CAM-02 baja de 0.35 a 0.30: recupera coches oscuros bajo los árboles.
- **Asignación por punto** (`asignar_por_punto`, por cámara): cada coche va al cajón que contiene el centro de lo que ocupa en el suelo. Con
  cajones de tamaños muy distintos por la perspectiva, el solape absoluto favorecía a los cajones cercanos, que son más grandes.
- **Panel en celular** (revisión de diseño): la navegación pasa a una barra fija abajo (con "Inicio" y "Admin" como nombres cortos), el
  encabezado se reduce de 233 a 57 px (el tema y "Salir" quedan arriba como botones compactos), en el Mapa las filas salen antes que el
  perímetro, los cajones miden 40 px en pantallas táctiles y ningún texto del panel baja de 12 px (los cajones del escritorio crecieron
  de 25 a 30 px).
- **Panel: estados que no dependen solo del color y contrastes de texto >= 4.5:1** (revisión de diseño). Libre = cajón hueco (relleno claro
  con aro), ocupado = macizo con un coche, obstruido = amarillo con "!", reservado = "R", fuera de servicio = "×"; en las barras y la gráfica,
  libre va rayado. Con deuteranopia simulada, libre y ocupado pasan de 1.04:1 a distinguirse a simple vista. Rellenos más oscuros
  (`#1E7D46`, `#C23030`, `#3B68C2`, `#6B7480`), texto marino sobre el naranja de la marca y naranja oscuro (`#B84508`) para texto
  naranja sobre blanco; el modo oscuro usa acentos más claros.
- **Etiquetado de coches** para ajustar el modelo (`docs/ETIQUETADO.md`): `scripts/preparar_etiquetado.py` saca 100 fotogramas de los videos
  reales y los pre-marca; `scripts/etiquetar_coches.py` abre una herramienta local en el navegador para corregir las cajas (dibujar,
  borrar, zoom, copiar de la anterior, deshacer). Todo queda en `datasets/etiquetado/`, fuera de Git.
- **CAM-02 con 51 cajones provisionales** en las filas 3 a 7, tomados de los coches que están quietos casi todo el video (la numeración
  de las filas, de derecha a izquierda, está por confirmar). Solo existen donde hay coche: los cajones vacíos aún no están dibujados.
- **Seguimiento de coches.** Cada vehículo detectado recibe un número que conserva entre fotogramas (`vision/parking_vision/seguimiento.py`)
  y se sabe si está en movimiento o quieto, desde cuándo y en qué cajón está (o si está fuera de todo cajón, también donde no hay
  cajones dibujados). El servidor de visión lo publica (`POST /ingest/vehiculos`), la API lo guarda solo en memoria
  (`GET /sistema/vehiculos`) y el panel lo muestra en Resumen ("Seguimiento de coches") y en el video (`#12`, y los minutos si lleva
  más de uno quieto). Un coche que ven dos cámaras a la vez se cuenta en las dos. Aún no genera eventos de entrada y salida del
  estacionamiento (la cámara `CAM-03` de la entrada es la candidata).
- **Detección por mosaicos** (`mosaicos` por cámara): la imagen se parte en recortes que se traslapan y se detecta en cada uno, además de la
  imagen completa; así se ven los coches chicos del lateral y del fondo. En la cámara general pasó de 21 a 58 coches con la misma
  confianza (y a 78 con `conf_seguimiento` 0.2, la confianza mínima de los coches que se siguen, más baja que la de ocupar un cajón).
  Siguen escapándose algunos coches grandes y cercanos vistos desde arriba (un SUV azul oscuro, un SUV blanco): para eso hace falta
  ajustar el modelo con fotogramas etiquetados de estas cámaras.
- **CAM-02 ve las filas 3 a 7 y el perímetro** (la fila 8 no la ve ninguna cámara). Los cajones que ninguna configuración de cámara define
  se reinician a "sin monitoreo" al iniciar (`python -m app.seed --vigilados`), así no quedan estados viejos de los videos de demostración.
- **"Fila" en lugar de "Isla"** en el panel, la app y los avisos: la isla A se muestra como "Fila 1", la B como "Fila 2", etc. (los
  cajones siguen llamándose `A-09`, `B-01`...), y la cámara `CAM-01` se llama "Fila 1 y 2". Internamente las zonas siguen siendo `A` a `H`.
- **Las únicas cámaras son 3, con grabaciones reales**: `CAM-01` "Isla 1 y 2" (2688×1512, ojo de pez), `CAM-02` "Estacionamiento"
  (vista general) y `CAM-03` "Entrada" (la pluma de la caseta, sin cajones). Los videos están en `datasets/reales/` (ignorado por Git) y
  `demo/cameras_reales.json` los configura; el panel y la app muestran el nombre de cada cámara. Sin los videos reales se usan los de demostración.
- **Una cámara puede ver varias islas.** Antes cada cámara era de una sola isla (`CAM-01` a `CAM-08`); ahora la cámara de cada cajón se
  asigna por cajón, las cámaras sobrantes se eliminan al iniciar y los avisos de isla llena se calculan por cada isla que ve la cámara.
  La isla 1 es la A (la más lejana a la cámara), la 2 la B, etc.; la isla 8 queda sin cámara por ahora.
- **Isla 1, fila c** (16 cajones, numerados desde el más lejano): se dibujaron a lo largo de la banqueta con perspectiva y entran 8 en el
  encuadre (`A-09` a `A-16`); los 8 más lejanos quedan sin monitoreo. En un fotograma de prueba los 3 coches de la fila caen en su cajón
  (con `occupied_ratio` 0.22 en `CAM-01`, porque los cajones son franjas largas). Isla 2: 16 cajones provisionales de los coches estacionados. YOLOv8n a 1920 px falla con algunos coches grandes
  vistos desde arriba y confunde objetos lejanos; se descargó `yolov8s.pt` para compararlo, sin una ventaja clara sin etiquetas.

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

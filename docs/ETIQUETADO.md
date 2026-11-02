# Etiquetar coches para mejorar el modelo

El modelo YOLO viene entrenado con fotos genéricas y se equivoca con las cámaras del IEST: se le escapan coches grandes vistos desde
arriba y cuenta mal los del lateral. Para corregirlo hay que enseñarle estas cámaras con fotogramas donde una persona marcó dónde está
cada coche.

## 1. Preparar los fotogramas (una vez)

```bash
python scripts/preparar_etiquetado.py
```

Saca 100 fotogramas repartidos por los videos reales (40 de la cámara "Fila 1 y 2", 50 de "Estacionamiento" y 10 de "Entrada") y los
pre-marca con el modelo actual. Quedan en `datasets/etiquetado/` (Git los ignora: llevan personas y placas).

## 2. Corregir las cajas

```bash
python scripts/etiquetar_coches.py
```

Abre `http://127.0.0.1:8200`. Solo escucha en este equipo y cada cambio se guarda solo. Las cajas rojas son coches y las azules motos.
Lo que hay que hacer en cada fotograma:

1. **Borrar** las cajas que no son un coche (clic derecho sobre la caja).
2. **Dibujar** las de los coches que faltan (arrastrar con el clic izquierdo; acércate con la rueda para los chicos del fondo).
3. **Ajustar** lo que esté mal: borrar la caja y volver a dibujarla.
4. **Enter**: marca el fotograma como revisado y pasa al siguiente sin revisar.

Atajos: `←` `→` cambian de fotograma · `C` copia las cajas del fotograma anterior de la misma cámara (los coches estacionados casi no
se mueven) · `1` coche, `2` moto · `Supr` borra la caja seleccionada · `Ctrl+Z` deshace · `H` oculta las cajas · `F` ajusta la imagen ·
`Mayús` + arrastrar mueve la imagen.

Una caja debe cubrir **todo el coche** (techo, parabrisas y llantas) y los coches tapados a medias por un árbol se marcan igual. Los
coches que se ven pero son del perímetro (junto a la banqueta de abajo) también se marcan: aquí se etiquetan *todos* los vehículos.

## 3. Entrenar

Con unos 40 fotogramas revisados ya se puede probar; con los 100, mejor. Después se entrena YOLOv8 con esas imágenes y se compara contra
el modelo actual sobre fotogramas que no se usaron para entrenar.

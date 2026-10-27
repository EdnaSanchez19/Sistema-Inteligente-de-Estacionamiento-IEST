# Dataset de Kaggle: Smart Parking Management

Archivo revisado: `IIoT_Smart_Parking_Management.csv`, de
[datasetengineer/smart-parking-management-dataset](https://www.kaggle.com/datasets/datasetengineer/smart-parking-management-dataset)
(1000 filas, 28 columnas). Los datos **no se incluyen** en el repositorio; solo un perfil agregado
(`demo/perfil_ocupacion.json`, generado con `scripts/perfil_dataset.py`).

## Qué contiene

Registros de un estacionamiento con sensores IIoT: proximidad, presión y ultrasonido; tipo de usuario (registrado,
visitante, personal) y de vehículo (auto, motocicleta, eléctrico); horas de entrada y salida; duración de la estancia;
ocupación; pagos, multas, clima, nivel de tráfico y tamaño del cajón. **No trae imágenes ni video.**

## Qué tan confiable es: es sintético

| Revisión | Resultado |
|---|---|
| ¿Los sensores distinguen ocupado de libre? | No: la diferencia entre ocupados y libres es casi nula (d de Cohen de 0.03 a 0.08 en proximidad, presión, ultrasonido y peso) |
| ¿Hay patrón por hora del día? | No: las horas de entrada son uniformes (χ² = 22 contra 23 esperado si fuera azar) |
| ¿Cada cajón pertenece a una sola sección? | No: los 50 cajones aparecen en más de una sección |
| ¿La salida es posterior a la entrada? | Solo en el 46 % de los registros |
| ¿Los cajones "reservados" están ocupados? | 72 de 157 aparecen vacíos |
| Fechas | 1000 registros a intervalos regulares de ~6.7 h entre 2021 y 2024 |

Conclusión: sirve para **darle forma a una simulación**, no como dato real ni para entrenar o validar nada.

## Qué se aprovechó

- **Duración de la estancia:** distribución con forma de campana, media de 2.87 h (el único atributo con estructura).
- **Ocupación media:** 55 %.
- **Mezcla de usuarios y vehículos:** 73 % registrados, 24 % visitantes, 3 % personal; 70 % autos, 19 % motocicletas,
  10 % eléctricos.

Se usan solo en el simulador opcional (`scripts/simulate_cameras.py`, `--con-simulacion`) para que los datos inventados
tengan una dinámica verosímil, y para repartir los 150 colgantes de muestra entre tipos.

## Qué no sirve para este proyecto

- **Entrenar o validar el modelo de visión:** no hay imágenes; el proyecto detecta con cámaras, no con sensores.
- **Fusión de sensores:** los sensores del dataset no tienen relación con la ocupación, así que no demuestran que un
  sensor ultrasónico o de presión aporte algo. Si el IEST instalara sensores, habría que probarlos con datos reales.
- **Predicción de demanda:** sin patrón horario, un modelo entrenado aquí aprendería ruido.

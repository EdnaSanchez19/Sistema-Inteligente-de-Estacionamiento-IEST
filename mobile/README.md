# App móvil — Estacionamiento IEST (tarea 3.1)

Interfaz en React Native (Expo + TypeScript). Por ahora funciona con datos de ejemplo
(`EXPO_PUBLIC_USE_MOCK=true`); en la tarea 3.5 se conecta a la API real.

## Pantallas

| Pantalla | Quién | Contenido |
|---|---|---|
| Login | todos | Acceso con correo institucional |
| Inicio | todos | Resumen general y disponibilidad por zona |
| Zonas | todos | Mapa de cajones por zona (libre / ocupado / obstruido / reservado / fuera de servicio); al tocar un cajón se ve cuánto lleva en su estado |
| Avisos | todos | Notificaciones del estacionamiento |
| Mi cuenta | todos | Espacio asignado y datos de vehículo/colgante |
| Admin | administradores | Historial de eventos y alertas de cámaras |

## Ejecutar

```bash
cd mobile
cp .env.example .env
npm install
npx expo start
```

Escanea el QR con Expo Go. En modo demo, cualquier correo entra como usuario; los que
empiezan con `admin` entran como administrador.

## Pendiente
- Colores institucionales y mockups finales (tarea 2.4): hoy los colores están en `src/theme.ts`.
- Gestión de usuarios/vehículos/colgantes para administradores (requiere API, tarea 3.4/3.5).

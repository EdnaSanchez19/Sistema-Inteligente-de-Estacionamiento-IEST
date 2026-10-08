import { AlertaCamara, Espacio, Evento, EstadoEspacio, Notificacion, TipoEspacio, Usuario, Vehiculo } from '../types';

const zonas = [
  { zona: 'A', cantidad: 20, tipoEspecial: 'discapacidad' as TipoEspacio },
  { zona: 'B', cantidad: 16, tipoEspecial: 'directivo' as TipoEspacio },
  { zona: 'C', cantidad: 12, tipoEspecial: 'visitante' as TipoEspacio },
];

// Estado pseudo-aleatorio pero estable (para que la UI no cambie en cada render)
const estadoDe = (n: number): EstadoEspacio => {
  const r = (n * 37) % 10;
  if (r === 0) return 'fuera_de_servicio';
  if (r === 1) return 'reservado';
  return r < 6 ? 'ocupado' : 'libre';
};

export const espacios: Espacio[] = zonas.flatMap(({ zona, cantidad, tipoEspecial }, zi) =>
  Array.from({ length: cantidad }, (_, i) => {
    const id = zi * 100 + i + 1;
    return {
      id,
      numero: `${zona}-${String(i + 1).padStart(2, '0')}`,
      zona,
      tipo: i < 2 ? tipoEspecial : ('general' as TipoEspacio),
      estado: estadoDe(id),
    };
  }),
);

export const usuarioDemo: Usuario = {
  id: 1,
  nombre: 'Usuario Demo',
  correo: 'demo@iest.edu.mx',
  rol: 'estudiante',
  espacioAsignado: 'A-03',
};

export const adminDemo: Usuario = { ...usuarioDemo, id: 2, nombre: 'Admin Demo', correo: 'admin@iest.edu.mx', rol: 'admin', espacioAsignado: null };

export const vehiculos: Vehiculo[] = [
  { id: 1, placa: 'ABC-123-D', marca: 'Nissan', modelo: 'Versa', color: 'Gris', colgante: { codigo: 'IEST-004512', tipo: 'Estudiante' } },
];

export const notificaciones: Notificacion[] = [
  { id: 1, titulo: 'Zona A casi llena', mensaje: 'Quedan menos de 3 espacios libres en la zona A.', fecha: new Date(Date.now() - 12 * 60_000).toISOString(), leida: false },
  { id: 2, titulo: 'Espacio asignado', mensaje: 'Tu espacio asignado es A-03.', fecha: new Date(Date.now() - 26 * 3600_000).toISOString(), leida: true },
];

export const eventos: Evento[] = [
  { id: 1, tipo: 'entrada', descripcion: 'Entrada vehículo colgante IEST-004512', fecha: new Date(Date.now() - 5 * 60_000).toISOString() },
  { id: 2, tipo: 'cambio_ocupacion', descripcion: 'Espacio B-04 pasó a ocupado', fecha: new Date(Date.now() - 9 * 60_000).toISOString() },
  { id: 3, tipo: 'error_deteccion', descripcion: 'Confianza baja en cámara CAM-02 (0.31)', fecha: new Date(Date.now() - 40 * 60_000).toISOString() },
  { id: 4, tipo: 'salida', descripcion: 'Salida vehículo colgante IEST-001873', fecha: new Date(Date.now() - 55 * 60_000).toISOString() },
];

export const alertasCamara: AlertaCamara[] = [
  { id: 1, camara: 'CAM-01', zona: 'A', estado: 'en_linea', ultimaSenal: new Date().toISOString() },
  { id: 2, camara: 'CAM-02', zona: 'B', estado: 'en_linea', ultimaSenal: new Date().toISOString() },
  { id: 3, camara: 'CAM-03', zona: 'C', estado: 'desconectada', ultimaSenal: new Date(Date.now() - 3 * 3600_000).toISOString() },
];

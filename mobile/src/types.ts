export type Rol = 'estudiante' | 'docente' | 'directivo' | 'administrativo' | 'externo' | 'admin';

export type EstadoEspacio = 'libre' | 'ocupado' | 'obstruido' | 'reservado' | 'fuera_de_servicio';
export type TipoEspacio = 'general' | 'discapacidad' | 'directivo' | 'visitante' | 'motocicleta';

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: Rol;
  espacioAsignado?: string | null;
}

export interface Espacio {
  id: number;
  numero: string;
  zona: string;
  tipo: TipoEspacio;
  estado: EstadoEspacio;
  /** false: ninguna cámara ha reportado este cajón; su estado no es una observación y se muestra "sin monitoreo" */
  monitoreado: boolean;
  actualizado?: string | null; // ISO
  /** desde cuándo está en este estado (ISO) y cuántos segundos lleva; para un coche, cuánto lleva estacionado */
  desde?: string | null;
  duracion_s?: number | null;
  /** true: la cámara vio el cambio y la duración es exacta; false: es "al menos" esa duración */
  desde_observado?: boolean;
  /** qué obstruye el cajón cuando está obstruido (persona, maleta…) */
  objeto?: string | null;
}

export interface ResumenZona {
  zona: string;
  total: number; // cajones de la isla
  monitoreados: number; // los que una cámara ya observa
  libres: number; // solo entre los monitoreados
  ocupados: number; // solo entre los monitoreados
  obstruidos: number; // con un objeto que no es vehículo dentro
}

export interface Vehiculo {
  id: number;
  placa: string;
  marca: string;
  modelo: string;
  color: string;
  colgante?: { codigo: string; tipo: string } | null;
}

export interface Notificacion {
  id: number;
  titulo: string;
  mensaje: string;
  fecha: string; // ISO
  leida: boolean;
}

export type TipoEvento = 'entrada' | 'salida' | 'cambio_ocupacion' | 'error_deteccion' | 'camara_desconectada' | 'camara_restablecida' | 'obstruccion' | 'obstruccion_retirada';

export interface Evento {
  id: number;
  tipo: TipoEvento;
  descripcion: string;
  fecha: string; // ISO
}

export interface AlertaCamara {
  id: number;
  camara: string;
  zona: string;
  estado: 'en_linea' | 'desconectada';
  ultimaSenal: string | null; // ISO
}

export const esAdmin = (u?: Usuario | null) => u?.rol === 'admin';

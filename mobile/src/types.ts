export type Rol = 'estudiante' | 'docente' | 'directivo' | 'administrativo' | 'externo' | 'admin';

export type EstadoEspacio = 'libre' | 'ocupado' | 'reservado' | 'fuera_de_servicio';
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
}

export interface ResumenZona {
  zona: string;
  total: number;
  libres: number;
  ocupados: number;
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

export type TipoEvento = 'entrada' | 'salida' | 'cambio_ocupacion' | 'error_deteccion' | 'camara_desconectada' | 'camara_restablecida';

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

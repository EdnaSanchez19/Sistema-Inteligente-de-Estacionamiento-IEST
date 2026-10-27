import * as mock from '../data/mock';
import { AlertaCamara, Espacio, Evento, Notificacion, ResumenZona, Usuario, Vehiculo } from '../types';

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const USE_MOCK = (process.env.EXPO_PUBLIC_USE_MOCK ?? 'false') === 'true';
const TIMEOUT_MS = 10_000;

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export const setToken = (t: string | null) => {
  token = t;
};
/** La sesión registra aquí qué hacer cuando el servidor responde 401 (token vencido o usuario desactivado). */
export const setUnauthorizedHandler = (fn: (() => void) | null) => {
  onUnauthorized = fn;
};

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    return await fetch(`${API_URL}${path}`, { ...init, signal: ctrl.signal });
  } catch {
    throw new Error('No se pudo conectar con el servidor. Revisa tu conexión.');
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) {
    onUnauthorized?.();
    throw new Error('Tu sesión expiró. Inicia sesión de nuevo.');
  }
  if (res.status === 403) throw new Error('No tienes permisos para ver esta información.');
  if (!res.ok) throw new Error(`El servidor respondió con error ${res.status}.`);
  return res.json() as Promise<T>;
}

const delay = <T,>(v: T, ms = 250) => new Promise<T>((r) => setTimeout(() => r(v), ms));

export const resumenPorZona = (espacios: Espacio[]): ResumenZona[] => {
  const zonas = [...new Set(espacios.map((e) => e.zona))].sort();
  return zonas.map((zona) => {
    const delaZona = espacios.filter((e) => e.zona === zona);
    // Solo cuentan los cajones que una cámara ya observó: los demás no tienen un estado real que mostrar.
    const vistos = delaZona.filter((e) => e.monitoreado && e.estado !== 'fuera_de_servicio');
    return {
      zona,
      total: delaZona.length,
      monitoreados: delaZona.filter((e) => e.monitoreado).length,
      libres: vistos.filter((e) => e.estado === 'libre').length,
      ocupados: vistos.filter((e) => e.estado === 'ocupado').length,
    };
  });
};

export const api = {
  async login(correo: string, password: string): Promise<{ token: string; usuario: Usuario }> {
    if (USE_MOCK) {
      const usuario = correo.startsWith('admin') ? mock.adminDemo : mock.usuarioDemo;
      return delay({ token: 'mock-token', usuario });
    }
    const res = await send('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: correo, password }).toString(),
    });
    if (res.status === 401) throw new Error('Correo o contraseña incorrectos');
    if (!res.ok) throw new Error(`El servidor respondió con error ${res.status}.`);
    const { access_token } = await res.json();
    setToken(access_token);
    return { token: access_token, usuario: await request<Usuario>('/auth/me') };
  },
  /** Recupera la sesión guardada: devuelve el usuario si el token sigue siendo válido. */
  async restaurar(savedToken: string): Promise<Usuario> {
    setToken(savedToken);
    return request<Usuario>('/auth/me');
  },
  espacios: (): Promise<Espacio[]> => (USE_MOCK ? delay(mock.espacios) : request('/espacios')),
  vehiculos: (): Promise<Vehiculo[]> => (USE_MOCK ? delay(mock.vehiculos) : request('/vehiculos/mios')),
  notificaciones: (): Promise<Notificacion[]> => (USE_MOCK ? delay(mock.notificaciones) : request('/notificaciones')),
  eventos: (): Promise<Evento[]> => (USE_MOCK ? delay(mock.eventos) : request('/eventos')),
  alertasCamara: (): Promise<AlertaCamara[]> => (USE_MOCK ? delay(mock.alertasCamara) : request('/camaras')),
};

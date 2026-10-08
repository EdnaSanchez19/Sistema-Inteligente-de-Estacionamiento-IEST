import * as mock from '../data/mock';
import { AlertaCamara, Espacio, Evento, Notificacion, ResumenZona, Usuario, Vehiculo } from '../types';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
const USE_MOCK = (process.env.EXPO_PUBLIC_USE_MOCK ?? 'true') === 'true';

let token: string | null = null;
export const setToken = (t: string | null) => {
  token = t;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`Error ${res.status} en ${path}`);
  return res.json() as Promise<T>;
}

const delay = <T,>(v: T, ms = 250) => new Promise<T>((r) => setTimeout(() => r(v), ms));

export const resumenPorZona = (espacios: Espacio[]): ResumenZona[] => {
  const zonas = [...new Set(espacios.map((e) => e.zona))].sort();
  return zonas.map((zona) => {
    const delaZona = espacios.filter((e) => e.zona === zona && e.estado !== 'fuera_de_servicio');
    return {
      zona,
      total: delaZona.length,
      libres: delaZona.filter((e) => e.estado === 'libre').length,
      ocupados: delaZona.filter((e) => e.estado === 'ocupado').length,
    };
  });
};

export const api = {
  async login(correo: string, password: string): Promise<{ token: string; usuario: Usuario }> {
    if (USE_MOCK) {
      const usuario = correo.startsWith('admin') ? mock.adminDemo : mock.usuarioDemo;
      return delay({ token: 'mock-token', usuario });
    }
    const form = new URLSearchParams({ username: correo, password });
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (!res.ok) throw new Error('Credenciales incorrectas');
    const data = await res.json();
    setToken(data.access_token);
    return { token: data.access_token, usuario: await request<Usuario>('/auth/me') };
  },
  espacios: (): Promise<Espacio[]> => (USE_MOCK ? delay(mock.espacios) : request('/espacios')),
  vehiculos: (): Promise<Vehiculo[]> => (USE_MOCK ? delay(mock.vehiculos) : request('/vehiculos/mios')),
  notificaciones: (): Promise<Notificacion[]> => (USE_MOCK ? delay(mock.notificaciones) : request('/notificaciones')),
  eventos: (): Promise<Evento[]> => (USE_MOCK ? delay(mock.eventos) : request('/eventos')),
  alertasCamara: (): Promise<AlertaCamara[]> => (USE_MOCK ? delay(mock.alertasCamara) : request('/camaras')),
};

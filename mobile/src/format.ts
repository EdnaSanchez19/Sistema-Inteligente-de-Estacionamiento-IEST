/** Cuánto lleva un cajón en su estado, en texto: 40 s, 12 min, 3 h 2 min, 2 d 1 h. */
export function duracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d} d ${h % 24} h` : `${d} d`;
}

/** "al menos 3 h" si la cámara no vio el momento en que llegó; "3 h" si sí. */
export function duracionDe(e: { duracion_s?: number | null; desde_observado?: boolean }): string | null {
  if (e.duracion_s == null) return null;
  return (e.desde_observado ? '' : 'al menos ') + duracion(e.duracion_s);
}

/** "Isla A" para una isla; las zonas del perímetro se llaman por su nombre ("Lateral caseta"). */
export const rotuloZona = (zona: string): string => (zona.length === 1 ? `Isla ${zona}` : zona);

/** Primero las islas (nombre de una letra) y luego el perímetro, cada grupo por orden alfabético. */
export const ordenarZonas = (zonas: string[]): string[] =>
  [...zonas].sort((a, b) => Number(a.length > 1) - Number(b.length > 1) || a.localeCompare(b));

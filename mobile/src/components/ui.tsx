import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { colors, radius, spacing } from '../theme';
import { EstadoEspacio } from '../types';

export const estadoColor: Record<EstadoEspacio, string> = {
  libre: colors.free,
  ocupado: colors.occupied,
  reservado: colors.reserved,
  fuera_de_servicio: colors.offline,
};

export const estadoTexto: Record<EstadoEspacio, string> = {
  libre: 'Libre',
  ocupado: 'Ocupado',
  reservado: 'Reservado',
  fuera_de_servicio: 'Fuera de servicio',
};

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function Badge({ text, color }: { text: string; color: string }) {
  return (
    <View style={[s.badge, { backgroundColor: color + '22' }]}>
      <Text style={[s.badgeText, { color }]}>{text}</Text>
    </View>
  );
}

export function OccupancyBar({ libres, ocupados, total }: { libres: number; ocupados: number; total: number }) {
  const pct = (n: number) => (total === 0 ? 0 : (n / total) * 100);
  return (
    <View style={s.barTrack}>
      <View style={{ width: `${pct(ocupados)}%`, backgroundColor: colors.occupied }} />
      <View style={{ width: `${pct(libres)}%`, backgroundColor: colors.free }} />
    </View>
  );
}

export function Legend() {
  return (
    <View style={s.legend}>
      {(Object.keys(estadoTexto) as EstadoEspacio[]).map((e) => (
        <View key={e} style={s.legendItem}>
          <View style={[s.dot, { backgroundColor: estadoColor[e] }]} />
          <Text style={s.legendText}>{estadoTexto[e]}</Text>
        </View>
      ))}
    </View>
  );
}

export function Title({ children }: { children: React.ReactNode }) {
  return <Text style={s.title}>{children}</Text>;
}

/** Carga datos asíncronos con soporte de pull-to-refresh. */
export function useLoad<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      setData(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
    }
  }, [fn]);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  return { data, error, refreshing, refresh };
}

export function Screen<T>({
  state,
  children,
}: {
  state: { data: T | null; error: string | null; refreshing: boolean; refresh: () => void };
  children: (data: T) => React.ReactNode;
}) {
  return (
    <ScrollView
      style={s.screen}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
      refreshControl={<RefreshControl refreshing={state.refreshing} onRefresh={state.refresh} />}
    >
      {state.error ? <Text style={s.error}>{state.error}</Text> : null}
      {state.data === null && !state.error ? <ActivityIndicator color={colors.primary} style={{ marginTop: 40 }} /> : null}
      {state.data !== null ? children(state.data) : null}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  card: { backgroundColor: colors.card, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999 },
  badgeText: { fontSize: 12, fontWeight: '600' },
  barTrack: { flexDirection: 'row', height: 10, borderRadius: 5, overflow: 'hidden', backgroundColor: colors.border },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendText: { fontSize: 12, color: colors.muted },
  dot: { width: 10, height: 10, borderRadius: 5 },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  error: { color: colors.occupied, textAlign: 'center' },
});

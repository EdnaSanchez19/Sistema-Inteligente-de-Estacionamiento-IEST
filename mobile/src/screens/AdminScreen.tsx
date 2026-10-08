import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Badge, Card, Screen, useLoad } from '../components/ui';
import { api } from '../services/api';
import { colors, spacing } from '../theme';
import { TipoEvento } from '../types';
import { formatoFecha } from './NotificationsScreen';

const eventoColor: Record<TipoEvento, string> = {
  entrada: colors.free,
  salida: colors.primary,
  cambio_ocupacion: colors.reserved,
  error_deteccion: colors.occupied,
  camara_desconectada: colors.occupied,
};

function Eventos() {
  const state = useLoad(api.eventos);
  return (
    <Screen state={state}>
      {(items) =>
        items.map((e) => (
          <Card key={e.id} style={{ gap: 6 }}>
            <View style={s.row}>
              <Badge text={e.tipo.replace(/_/g, ' ')} color={eventoColor[e.tipo]} />
              <Text style={s.date}>{formatoFecha(e.fecha)}</Text>
            </View>
            <Text style={s.text}>{e.descripcion}</Text>
          </Card>
        ))
      }
    </Screen>
  );
}

function Camaras() {
  const state = useLoad(api.alertasCamara);
  return (
    <Screen state={state}>
      {(items) =>
        items.map((c) => (
          <Card key={c.id} style={{ gap: 6 }}>
            <View style={s.row}>
              <Text style={s.cam}>
                {c.camara} · Zona {c.zona}
              </Text>
              <Badge text={c.estado === 'en_linea' ? 'En línea' : 'Desconectada'} color={c.estado === 'en_linea' ? colors.free : colors.occupied} />
            </View>
            <Text style={s.date}>Última señal: {c.ultimaSenal ? formatoFecha(c.ultimaSenal) : 'sin señal'}</Text>
          </Card>
        ))
      }
    </Screen>
  );
}

export default function AdminScreen() {
  const [tab, setTab] = useState<'eventos' | 'camaras'>('eventos');
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={s.tabs}>
        {(['eventos', 'camaras'] as const).map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} style={[s.tab, tab === t && s.tabOn]}>
            <Text style={[s.tabText, tab === t && { color: '#fff' }]}>{t === 'eventos' ? 'Historial de eventos' : 'Alertas de cámaras'}</Text>
          </Pressable>
        ))}
      </View>
      {tab === 'eventos' ? <Eventos /> : <Camaras />}
    </View>
  );
}

const s = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: spacing.sm, padding: spacing.lg, paddingBottom: 0 },
  tab: { flex: 1, padding: spacing.md, borderRadius: 999, backgroundColor: colors.card, alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  tabOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { fontWeight: '600', color: colors.text, fontSize: 13 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  date: { color: colors.muted, fontSize: 12 },
  text: { color: colors.text },
  cam: { fontWeight: '700', color: colors.text },
});

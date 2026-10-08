import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Card, Screen, useLoad } from '../components/ui';
import { api } from '../services/api';
import { colors } from '../theme';

export const formatoFecha = (iso: string) =>
  new Date(iso).toLocaleString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

export default function NotificationsScreen() {
  const state = useLoad(api.notificaciones);
  return (
    <Screen state={state}>
      {(items) =>
        items.length === 0 ? (
          <Text style={s.empty}>No tienes notificaciones.</Text>
        ) : (
          items.map((n) => (
            <Card key={n.id} style={!n.leida ? s.unread : undefined}>
              <View style={s.row}>
                <Text style={s.title}>{n.titulo}</Text>
                <Text style={s.date}>{formatoFecha(n.fecha)}</Text>
              </View>
              <Text style={s.msg}>{n.mensaje}</Text>
            </Card>
          ))
        )
      }
    </Screen>
  );
}

const s = StyleSheet.create({
  unread: { borderLeftWidth: 4, borderLeftColor: colors.accent },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  title: { fontWeight: '700', color: colors.text, flexShrink: 1 },
  date: { color: colors.muted, fontSize: 12 },
  msg: { color: colors.text, marginTop: 4 },
  empty: { textAlign: 'center', color: colors.muted, marginTop: 40 },
});

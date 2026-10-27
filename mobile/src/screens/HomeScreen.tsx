import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Card, Legend, OccupancyBar, Screen, Title, useLoad } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { api, resumenPorZona } from '../services/api';
import { colors, spacing } from '../theme';

export default function HomeScreen() {
  const { usuario } = useAuth();
  const state = useLoad(api.espacios, 15_000);

  return (
    <Screen state={state}>
      {(espacios) => {
        const zonas = resumenPorZona(espacios);
        const total = zonas.reduce((a, z) => a + z.total, 0);
        const libres = zonas.reduce((a, z) => a + z.libres, 0);
        const ocupados = zonas.reduce((a, z) => a + z.ocupados, 0);
        return (
          <>
            <Text style={s.hello}>Hola, {usuario?.nombre.split(' ')[0]}</Text>
            <Card style={{ gap: spacing.md }}>
              <Text style={s.muted}>Espacios disponibles</Text>
              <Text style={s.big}>
                {libres} <Text style={s.of}>de {total}</Text>
              </Text>
              <OccupancyBar libres={libres} ocupados={ocupados} total={total} />
              <Legend />
            </Card>
            {usuario?.espacioAsignado ? (
              <Card>
                <Text style={s.muted}>Tu espacio asignado</Text>
                <Text style={s.assigned}>{usuario.espacioAsignado}</Text>
              </Card>
            ) : null}
            <Title>Por isla</Title>
            {zonas.map((z) => (
              <Card key={z.zona} style={{ gap: spacing.sm }}>
                <View style={s.row}>
                  <Text style={s.zone}>Isla {z.zona}</Text>
                  <Text style={[s.free, z.libres === 0 && { color: colors.occupied }]}>{z.libres} libres</Text>
                </View>
                <OccupancyBar libres={z.libres} ocupados={z.ocupados} total={z.total} />
              </Card>
            ))}
          </>
        );
      }}
    </Screen>
  );
}

const s = StyleSheet.create({
  hello: { fontSize: 22, fontWeight: '700', color: colors.text },
  muted: { color: colors.muted },
  big: { fontSize: 48, fontWeight: '800', color: colors.primary },
  of: { fontSize: 18, fontWeight: '500', color: colors.muted },
  assigned: { fontSize: 28, fontWeight: '800', color: colors.accent },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  zone: { fontSize: 16, fontWeight: '600', color: colors.text },
  free: { color: colors.free, fontWeight: '700' },
});

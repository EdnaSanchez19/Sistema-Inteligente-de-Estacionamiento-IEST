import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Legend, Screen, estadoColor, useLoad } from '../components/ui';
import { api } from '../services/api';
import { colors, radius, spacing } from '../theme';
import { TipoEspacio } from '../types';

const tipoEtiqueta: Record<TipoEspacio, string> = {
  general: '',
  discapacidad: '♿',
  directivo: '★',
  visitante: 'V',
  motocicleta: 'M',
};

export default function ZonesScreen() {
  const state = useLoad(api.espacios, 15_000);
  const [zona, setZona] = useState<string | null>(null);

  return (
    <Screen state={state}>
      {(espacios) => {
        const zonas = [...new Set(espacios.map((e) => e.zona))].sort();
        const actual = zona ?? zonas[0];
        const lista = espacios.filter((e) => e.zona === actual);
        return (
          <>
            <View style={s.chips}>
              {zonas.map((z) => (
                <Pressable key={z} onPress={() => setZona(z)} style={[s.chip, z === actual && s.chipOn]}>
                  <Text style={[s.chipText, z === actual && { color: '#fff' }]}>Isla {z}</Text>
                </Pressable>
              ))}
            </View>
            <Card style={{ gap: spacing.md }}>
              <Legend />
              <View style={s.grid}>
                {lista.map((e) => (
                  <View key={e.id} style={[s.cell, { backgroundColor: estadoColor[e.estado] }]}>
                    <Text style={s.cellNum}>{e.numero.split('-')[1]}</Text>
                    {tipoEtiqueta[e.tipo] ? <Text style={s.cellTipo}>{tipoEtiqueta[e.tipo]}</Text> : null}
                  </View>
                ))}
              </View>
            </Card>
          </>
        );
      }}
    </Screen>
  );
}

const s = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontWeight: '600', color: colors.text },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  cell: { width: 40, height: 46, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center' },
  cellNum: { color: '#fff', fontWeight: '800', fontSize: 16 },
  cellTipo: { color: '#fff', fontSize: 12 },
});

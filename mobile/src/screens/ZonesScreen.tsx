import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Legend, Screen, estadoColor, estadoTexto, useLoad } from '../components/ui';
import { duracionDe } from '../format';
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
  const [elegido, setElegido] = useState<string | null>(null);

  return (
    <Screen state={state}>
      {(espacios) => {
        const zonas = [...new Set(espacios.map((e) => e.zona))].sort();
        const actual = zona ?? zonas[0];
        const lista = espacios.filter((e) => e.zona === actual);
        const monitoreados = lista.filter((e) => e.monitoreado).length;
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
              <Text style={s.cobertura}>
                {monitoreados === 0 ? 'Esta isla aún no tiene cámara' : `Cobertura: ${monitoreados} de ${lista.length} cajones monitoreados`}
              </Text>
              <Legend />
              <View style={s.grid}>
                {lista.map((e) => (
                  <Pressable key={e.id} onPress={() => setElegido(e.numero)} style={[s.cell, e.monitoreado ? { backgroundColor: estadoColor[e.estado] } : s.cellSin, e.numero === elegido && s.cellElegida]}>
                    <Text style={[s.cellNum, !e.monitoreado && { color: colors.muted, fontWeight: '500' }]}>{e.numero.split('-')[1]}</Text>
                    {tipoEtiqueta[e.tipo] ? <Text style={[s.cellTipo, !e.monitoreado && { color: colors.muted }]}>{tipoEtiqueta[e.tipo]}</Text> : null}
                  </Pressable>
                ))}
              </View>
              {(() => {
                const e = lista.find((x) => x.numero === elegido);
                if (!e) return <Text style={s.cobertura}>Toca un cajón para ver cuánto tiempo lleva en su estado.</Text>;
                if (!e.monitoreado) return <Text style={s.detalle}>{e.numero} · sin monitoreo (ninguna cámara lo observa)</Text>;
                const tiempo = duracionDe(e);
                const que = e.estado === 'obstruido' && e.objeto ? ` (${e.objeto})` : '';
                const verbo = e.estado === 'ocupado' ? 'estacionado' : 'así';
                return <Text style={s.detalle}>{e.numero} · {estadoTexto[e.estado]}{que}{tiempo ? ` · lleva ${verbo} ${tiempo}` : ''}</Text>;
              })()}
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
  cellElegida: { borderWidth: 2, borderColor: colors.text },
  detalle: { color: colors.text, fontWeight: '600', fontSize: 14 },
  cellSin: { borderWidth: 1, borderStyle: 'dashed', borderColor: colors.offline, backgroundColor: colors.bg },
  cobertura: { color: colors.muted, fontSize: 13 },
  cellNum: { color: '#fff', fontWeight: '800', fontSize: 16 },
  cellTipo: { color: '#fff', fontSize: 12 },
});

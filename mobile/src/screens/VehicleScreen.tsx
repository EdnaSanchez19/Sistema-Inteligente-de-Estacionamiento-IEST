import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Badge, Card, Screen, Title, useLoad } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { colors, spacing } from '../theme';

export default function VehicleScreen() {
  const { usuario, logout } = useAuth();
  const state = useLoad(api.vehiculos);

  return (
    <Screen state={state}>
      {(vehiculos) => (
        <>
          <Card>
            <Text style={s.name}>{usuario?.nombre}</Text>
            <Text style={s.muted}>{usuario?.correo}</Text>
            <View style={{ marginTop: spacing.sm }}>
              <Badge text={usuario?.rol ?? ''} color={colors.primary} />
            </View>
            {usuario?.espacioAsignado ? <Text style={s.assigned}>Espacio asignado: {usuario.espacioAsignado}</Text> : null}
          </Card>
          <Title>Mis vehículos</Title>
          {vehiculos.length === 0 ? <Text style={s.muted}>Aún no tienes vehículos registrados.</Text> : null}
          {vehiculos.map((v) => (
            <Card key={v.id} style={{ gap: 4 }}>
              <Text style={s.plate}>{v.placa}</Text>
              <Text style={s.text}>
                {v.marca} {v.modelo} · {v.color}
              </Text>
              {v.colgante ? (
                <Text style={s.muted}>
                  Colgante {v.colgante.codigo} ({v.colgante.tipo})
                </Text>
              ) : (
                <Badge text="Sin colgante" color={colors.reserved} />
              )}
            </Card>
          ))}
          <Text style={s.logout} onPress={logout}>
            Cerrar sesión
          </Text>
        </>
      )}
    </Screen>
  );
}

const s = StyleSheet.create({
  name: { fontSize: 20, fontWeight: '700', color: colors.text },
  muted: { color: colors.muted },
  text: { color: colors.text },
  assigned: { marginTop: spacing.md, color: colors.accent, fontWeight: '700' },
  plate: { fontSize: 22, fontWeight: '800', color: colors.primary, letterSpacing: 1 },
  logout: { color: colors.occupied, textAlign: 'center', fontWeight: '600', marginTop: spacing.lg, padding: spacing.md },
});

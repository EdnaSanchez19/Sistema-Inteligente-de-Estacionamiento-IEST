import React, { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useAuth } from '../context/AuthContext';
import { colors, radius, spacing } from '../theme';

export default function LoginScreen() {
  const { login } = useAuth();
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const entrar = async () => {
    setCargando(true);
    setError(null);
    try {
      await login(correo.trim(), password);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión');
    } finally {
      setCargando(false);
    }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={s.container}>
      <View style={s.header}>
        <Text style={s.logo}>P</Text>
        <Text style={s.brand}>Estacionamiento IEST</Text>
        <Text style={s.sub}>Consulta la disponibilidad en tiempo real</Text>
      </View>
      <View style={s.form}>
        <TextInput
          style={s.input}
          placeholder="Correo institucional"
          autoCapitalize="none"
          keyboardType="email-address"
          value={correo}
          onChangeText={setCorreo}
        />
        <TextInput style={s.input} placeholder="Contraseña" secureTextEntry value={password} onChangeText={setPassword} />
        {error ? <Text style={s.error}>{error}</Text> : null}
        <Pressable style={[s.button, (!correo || !password) && { opacity: 0.5 }]} disabled={!correo || !password || cargando} onPress={entrar}>
          {cargando ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Iniciar sesión</Text>}
        </Pressable>
        <Text style={s.hint}>Modo demo: cualquier correo; los que empiezan con "admin" entran como administrador.</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary, justifyContent: 'center', padding: spacing.xl },
  header: { alignItems: 'center', marginBottom: spacing.xl },
  logo: { width: 72, height: 72, lineHeight: 72, textAlign: 'center', borderRadius: 36, backgroundColor: colors.accent, color: '#fff', fontSize: 40, fontWeight: '800', overflow: 'hidden' },
  brand: { color: '#fff', fontSize: 24, fontWeight: '700', marginTop: spacing.md },
  sub: { color: '#C9D4EA', marginTop: 4 },
  form: { backgroundColor: '#fff', borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: spacing.md, fontSize: 16 },
  button: { backgroundColor: colors.accent, borderRadius: radius.sm, padding: spacing.md, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: colors.occupied, textAlign: 'center' },
  hint: { color: colors.muted, fontSize: 12, textAlign: 'center' },
});

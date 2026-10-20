import * as SecureStore from 'expo-secure-store';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { USE_MOCK, api, setToken, setUnauthorizedHandler } from '../services/api';
import { Usuario } from '../types';

const TOKEN_KEY = 'sesion_token';

interface AuthState {
  usuario: Usuario | null;
  /** true mientras se intenta recuperar la sesión guardada al abrir la app */
  cargando: boolean;
  login: (correo: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// SecureStore guarda el token cifrado (Keychain/Keystore). Si no está disponible, la sesión simplemente no persiste.
const guardar = (t: string | null) =>
  (t ? SecureStore.setItemAsync(TOKEN_KEY, t) : SecureStore.deleteItemAsync(TOKEN_KEY)).catch(() => undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(!USE_MOCK);

  const logout = useCallback(() => {
    setToken(null);
    setUsuario(null);
    guardar(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (USE_MOCK) return;
    (async () => {
      try {
        const saved = await SecureStore.getItemAsync(TOKEN_KEY);
        if (saved) setUsuario(await api.restaurar(saved));
      } catch {
        setToken(null);
        await guardar(null);
      } finally {
        setCargando(false);
      }
    })();
  }, []);

  const login = useCallback(async (correo: string, password: string) => {
    const res = await api.login(correo, password);
    setToken(res.token);
    setUsuario(res.usuario);
    if (!USE_MOCK) await guardar(res.token);
  }, []);

  const value = useMemo(() => ({ usuario, cargando, login, logout }), [usuario, cargando, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return ctx;
}

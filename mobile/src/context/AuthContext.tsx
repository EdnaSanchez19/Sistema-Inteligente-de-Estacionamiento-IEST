import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { api, setToken } from '../services/api';
import { Usuario } from '../types';

interface AuthState {
  usuario: Usuario | null;
  login: (correo: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);

  const login = useCallback(async (correo: string, password: string) => {
    const res = await api.login(correo, password);
    setToken(res.token);
    setUsuario(res.usuario);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUsuario(null);
  }, []);

  const value = useMemo(() => ({ usuario, login, logout }), [usuario, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return ctx;
}

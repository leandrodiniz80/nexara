"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import * as authApi from "@/lib/api/auth";
import type { MeResponse } from "@/lib/api/types";
import { clearToken, getToken, setToken } from "@/lib/auth/token";

interface AuthContextValue {
  user: MeResponse | null;
  /** True only while the initial session check (on load/refresh) is running. */
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const token = getToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        // Stored token is missing, expired, or the backend process restarted
        // (sessions are in-memory server-side) — either way it's no longer
        // valid, so drop it rather than keep resending a dead credential.
        clearToken();
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const session = await authApi.login({ email, password });
    setToken(session.token);
    const me = await authApi.me();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Always clear the local session, even if the network call fails —
      // an unreachable backend shouldn't be able to trap a user logged in.
      clearToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: user !== null, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

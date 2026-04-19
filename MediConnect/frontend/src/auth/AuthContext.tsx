import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, getAccessToken, setAccessToken } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { Me } from "../lib/types";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; me: Me };

type AuthContextValue = {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  async function refreshMe() {
    const token = getAccessToken();
    if (!token) {
      setState({ status: "anonymous" });
      return;
    }
    try {
      const me = await api<Me>("/me");
      setState({ status: "authenticated", me });
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 401) {
        setAccessToken(null);
        setState({ status: "anonymous" });
        return;
      }
      throw e;
    }
  }

  async function login(username: string, password: string) {
    const res = await api<{ access_token: string; token_type: string }>("/auth/token", {
      method: "POST",
      form: { username, password },
    });
    setAccessToken(res.access_token);
    await refreshMe();
  }

  function logout() {
    setAccessToken(null);
    setState({ status: "anonymous" });
  }

  useEffect(() => {
    void refreshMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AuthContextValue>(() => ({ state, login, logout, refreshMe }), [state]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}


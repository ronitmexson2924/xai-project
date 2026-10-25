"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  api,
  ApiException,
  LoginRequest,
  RegisterRequest,
  setStoredToken,
  UserResponse,
} from "./api";

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  giveConsent: () => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const savedToken = localStorage.getItem("pcg_token");
    if (!savedToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      setToken(savedToken);
      const me = await api.auth.getMe(savedToken);
      setUser(me);
    } catch {
      setStoredToken(null);
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Defer execution so it's not called synchronously in effect setup
    const timer = setTimeout(() => {
      void refreshUser();
    }, 0);
    return () => clearTimeout(timer);
  }, [refreshUser]);

  const login = async (data: LoginRequest) => {
    const res = await api.auth.login(data);
    setStoredToken(res.token);
    setToken(res.token);
    setUser(res.user);
  };

  const register = async (data: RegisterRequest) => {
    const res = await api.auth.register(data);
    setStoredToken(res.token);
    setToken(res.token);
    setUser(res.user);
  };

  const giveConsent = async () => {
    const res = await api.auth.consent();
    if (user) {
      setUser({
        ...user,
        consent_at: res.consent_at,
      });
    }
  };

  const logout = () => {
    setStoredToken(null);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        giveConsent,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export { ApiException };

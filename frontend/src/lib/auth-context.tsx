"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  api,
  ApiException,
  LoginRequest,
  RegisterRequest,
  setStoredToken,
  setUnauthorizedHandler,
  getStoredToken,
  UserResponse,
} from "./api";

interface AuthContextType {
  user: UserResponse | null;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<UserResponse>;
  register: (data: RegisterRequest) => Promise<UserResponse>;
  giveConsent: () => Promise<void>;
  markOnboarded: () => void;
  logout: () => Promise<void>;
  withdraw: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const saved = getStoredToken();
    if (!saved) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      setUser(await api.auth.me(saved));
    } catch {
      setStoredToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // an expired or revoked token anywhere in the app logs the user out locally
    setUnauthorizedHandler(() => setUser(null));
    const timer = setTimeout(() => void refreshUser(), 0);
    return () => {
      clearTimeout(timer);
      setUnauthorizedHandler(null);
    };
  }, [refreshUser]);

  const login = async (data: LoginRequest) => {
    const res = await api.auth.login(data);
    setStoredToken(res.token);
    setUser(res.user);
    return res.user;
  };

  const register = async (data: RegisterRequest) => {
    const res = await api.auth.register(data);
    setStoredToken(res.token);
    setUser(res.user);
    return res.user;
  };

  const giveConsent = async () => {
    const res = await api.auth.consent();
    setUser((current) => (current ? { ...current, consent_at: res.consent_at } : current));
  };

  const markOnboarded = () => setUser((current) => (current ? { ...current, onboarded: true } : current));

  const logout = async () => {
    try {
      await api.auth.logout(); // revokes the token on the server too
    } catch {
      // already invalid or offline: forgetting it locally is enough
    }
    setStoredToken(null);
    setUser(null);
  };

  const withdraw = async () => {
    await api.auth.deleteMe();
    setStoredToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, login, register, giveConsent, markOnboarded, logout, withdraw, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

export { ApiException };

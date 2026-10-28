"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  api,
  ApiException,
  LoginRequest,
  RegisterRequest,
  forgetLegacyToken,
  setUnauthorizedHandler,
  UserResponse,
} from "./api";

interface AuthContextType {
  user: UserResponse | null;
  isLoading: boolean;
  /** true after the user logged out or withdrew on purpose (pages then go to the landing page, not login) */
  signedOut: boolean;
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
  const [signedOut, setSignedOut] = useState(false);

  const refreshUser = useCallback(async () => {
    try {
      // the session is an httpOnly cookie this code cannot see: ask the server whose it is
      setUser(await api.auth.me());
    } catch {
      // not signed in (401), or offline
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // an expired or revoked session anywhere in the app logs the user out locally
    setUnauthorizedHandler(() => setUser(null));
    forgetLegacyToken();
    const timer = setTimeout(() => void refreshUser(), 0);
    return () => {
      clearTimeout(timer);
      setUnauthorizedHandler(null);
    };
  }, [refreshUser]);

  const login = async (data: LoginRequest) => {
    const res = await api.auth.login(data);
    setSignedOut(false);
    setUser(res.user);
    return res.user;
  };

  const register = async (data: RegisterRequest) => {
    const res = await api.auth.register(data);
    setSignedOut(false);
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
      await api.auth.logout(); // revokes the token on the server and clears the session cookie
    } catch {
      // already invalid or offline: forgetting the user locally is enough
    }
    setSignedOut(true);
    setUser(null);
  };

  const withdraw = async () => {
    await api.auth.deleteMe();
    setSignedOut(true);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, signedOut, login, register, giveConsent, markOnboarded, logout, withdraw, refreshUser }}
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

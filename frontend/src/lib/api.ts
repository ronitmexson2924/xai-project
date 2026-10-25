import type { paths } from "./api.d";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiError {
  code: string;
  message: string;
}

export class ApiException extends Error {
  code: string;
  status: number;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiException";
    this.code = error.code;
    this.status = status;
  }
}

export type RegisterRequest =
  paths["/api/v1/auth/register"]["post"]["requestBody"]["content"]["application/json"];
export type RegisterResponse =
  paths["/api/v1/auth/register"]["post"]["responses"]["201"]["content"]["application/json"];

export type LoginRequest =
  paths["/api/v1/auth/login"]["post"]["requestBody"]["content"]["application/json"];
export type LoginResponse =
  paths["/api/v1/auth/login"]["post"]["responses"]["200"]["content"]["application/json"];

export type ConsentResponse =
  paths["/api/v1/auth/consent"]["post"]["responses"]["200"]["content"]["application/json"];

export type UserResponse =
  paths["/api/v1/auth/me"]["get"]["responses"]["200"]["content"]["application/json"];

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pcg_token");
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("pcg_token", token);
  } else {
    localStorage.removeItem("pcg_token");
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  tokenOverride?: string | null
): Promise<T> {
  const token = tokenOverride !== undefined ? tokenOverride : getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 204) {
    return {} as T;
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const error: ApiError = data?.error || {
      code: "UNKNOWN_ERROR",
      message: res.statusText || "An unexpected error occurred",
    };
    throw new ApiException(res.status, error);
  }

  return data as T;
}

export const api = {
  auth: {
    register: (payload: RegisterRequest) =>
      request<RegisterResponse>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    login: (payload: LoginRequest) =>
      request<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    consent: () =>
      request<ConsentResponse>("/api/v1/auth/consent", {
        method: "POST",
        body: JSON.stringify({}),
      }),

    getMe: (token?: string) =>
      request<UserResponse>("/api/v1/auth/me", { method: "GET" }, token),

    deleteMe: () =>
      request<void>("/api/v1/me", {
        method: "DELETE",
      }),
  },

  health: () =>
    request<{ status: string; version: string }>("/health", { method: "GET" }),
};

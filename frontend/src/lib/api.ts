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

// Auth types
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

// Onboarding types
export type QuestionnaireItem =
  paths["/api/v1/onboarding/questionnaire"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type StateDelta =
  paths["/api/v1/onboarding/questionnaire"]["post"]["responses"]["200"]["content"]["application/json"];

// Session types
export type NextStepResponse =
  paths["/api/v1/session/next"]["post"]["responses"]["200"]["content"]["application/json"];
export type PublicItem = NonNullable<NextStepResponse["item"]>;
export type Recommendation = NextStepResponse["recommendation"];
export type ReasonEvidence = Recommendation["reasons"][number];

// Attempts types
export type AttemptIn =
  paths["/api/v1/attempts"]["post"]["requestBody"]["content"]["application/json"];
export type AttemptResult =
  paths["/api/v1/attempts"]["post"]["responses"]["200"]["content"]["application/json"];

// Explanation & Telemetry types
export type Explanation =
  paths["/api/v1/explanations/{explanation_id}"]["get"]["responses"]["200"]["content"]["application/json"];
export type EventBatchIn =
  paths["/api/v1/explanations/{explanation_id}/events"]["post"]["requestBody"]["content"]["application/json"];
export type EventBatchResponse =
  paths["/api/v1/explanations/{explanation_id}/events"]["post"]["responses"]["200"]["content"]["application/json"];
export type ExplanationFeedbackSummary =
  paths["/api/v1/explanations/{explanation_id}/close"]["post"]["responses"]["200"]["content"]["application/json"];

// Learner State & History types
export type LearnerState =
  paths["/api/v1/learners/me/state"]["get"]["responses"]["200"]["content"]["application/json"];
export type StateUpdateView =
  paths["/api/v1/learners/me/history"]["get"]["responses"]["200"]["content"]["application/json"][number];

// Graph & Admin types
export type GraphResponse =
  paths["/api/v1/graph"]["get"]["responses"]["200"]["content"]["application/json"];
export type AdminMetricsResponse =
  paths["/api/v1/admin/metrics"]["get"]["responses"]["200"]["content"]["application/json"];

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

  onboarding: {
    getQuestionnaire: () =>
      request<QuestionnaireItem[]>("/api/v1/onboarding/questionnaire", {
        method: "GET",
      }),

    submitQuestionnaire: (answers: Record<string, number>) =>
      request<StateDelta>("/api/v1/onboarding/questionnaire", {
        method: "POST",
        body: JSON.stringify({ answers }),
      }),
  },

  session: {
    next: () =>
      request<NextStepResponse>("/api/v1/session/next", {
        method: "POST",
        body: JSON.stringify({}),
      }),
  },

  attempts: {
    submit: (payload: AttemptIn) =>
      request<AttemptResult>("/api/v1/attempts", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  explanations: {
    get: (id: string) =>
      request<Explanation>(`/api/v1/explanations/${id}`, {
        method: "GET",
      }),

    sendEvents: (id: string, events: EventBatchIn["events"]) =>
      request<EventBatchResponse>(`/api/v1/explanations/${id}/events`, {
        method: "POST",
        body: JSON.stringify({ events }),
      }),

    close: (id: string) =>
      request<ExplanationFeedbackSummary>(`/api/v1/explanations/${id}/close`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
  },

  learners: {
    getState: () =>
      request<LearnerState>("/api/v1/learners/me/state", {
        method: "GET",
      }),

    getHistory: () =>
      request<StateUpdateView[]>("/api/v1/learners/me/history", {
        method: "GET",
      }),
  },

  graph: {
    get: () =>
      request<GraphResponse>("/api/v1/graph", {
        method: "GET",
      }),
  },

  admin: {
    getMetrics: () =>
      request<AdminMetricsResponse>("/api/v1/admin/metrics", {
        method: "GET",
      }),
  },

  health: () =>
    request<{ status: string; version: string }>("/health", { method: "GET" }),
};

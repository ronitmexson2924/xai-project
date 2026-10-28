import type { paths } from "./api.d";

/**
 * Every call goes to this app's own /api/v1 route (src/app/api/[...path]/route.ts), which forwards
 * it to the API server. The login token lives in an httpOnly cookie that this code never sees.
 */
const LEGACY_TOKEN_KEY = "pcg_token";

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

type Json<P extends keyof paths, M extends keyof paths[P], S extends number> = paths[P][M] extends {
  responses: { [K in S]: { content: { "application/json": infer T } } };
}
  ? T
  : never;
type Body<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  requestBody: { content: { "application/json": infer T } };
}
  ? T
  : never;

// Auth
export type RegisterRequest = Body<"/api/v1/auth/register", "post">;
// the token itself stays in the session cookie (src/app/api/[...path]/route.ts)
export type RegisterResponse = Omit<Json<"/api/v1/auth/register", "post", 201>, "token">;
export type LoginRequest = Body<"/api/v1/auth/login", "post">;
export type LoginResponse = Omit<Json<"/api/v1/auth/login", "post", 200>, "token">;
export type ConsentResponse = Json<"/api/v1/auth/consent", "post", 200>;
export type UserResponse = Json<"/api/v1/auth/me", "get", 200>;

// Onboarding
export type QuestionnaireItem = Json<"/api/v1/onboarding/questionnaire", "get", 200>[number];
export type StateDelta = Json<"/api/v1/onboarding/questionnaire", "post", 200>;

// Session and answers
export type NextStepResponse = Json<"/api/v1/session/next", "post", 200>;
export type PublicItem = NonNullable<NextStepResponse["item"]>;
export type Recommendation = NextStepResponse["recommendation"];
export type ReasonEvidence = Recommendation["reasons"][number];
export type AttemptIn = Body<"/api/v1/attempts", "post">;
export type AttemptResult = Json<"/api/v1/attempts", "post", 200>;
export type ChangeNotice = NonNullable<AttemptResult["change"]>;

// Explanations and telemetry
export type Explanation = Json<"/api/v1/explanations/{explanation_id}", "get", 200>;
export type EventBatchIn = Body<"/api/v1/explanations/{explanation_id}/events", "post">;
export type ExplanationEvent = EventBatchIn["events"][number];
export type EventBatchResponse = Json<"/api/v1/explanations/{explanation_id}/events", "post", 200>;
export type FeedbackOut = Json<"/api/v1/explanations/{explanation_id}/close", "post", 200>;

// Explainability (XAI E1-E5)
export type RecommendationWhy = Json<"/api/v1/recommendations/{recommendation_id}/why", "get", 200>;
export type BeliefExplanation = Json<"/api/v1/learners/me/explain", "get", 200>;

// The performance model (a trained neural network) and its SHAP / LIME / LRP / DiCE explanations
export type ModelInsight = Json<"/api/v1/recommendations/{recommendation_id}/model", "get", 200>;
export type MethodAttribution = ModelInsight["attributions"][number];
export type ModelCounterfactual = ModelInsight["counterfactuals"][number];
export type CounterfactualChange = ModelCounterfactual["changes"][number];
export interface ModelMetrics {
  auc: number;
  log_loss: number;
  brier: number;
  accuracy: number;
  ece: number;
}
export interface ModelCard {
  name: string;
  task: string;
  architecture: string;
  trained_on: string;
  trained_at: string;
  rows: { train: number; validation: number; test: number };
  learners: { train: number; validation: number; test: number };
  base_rate: number;
  model_selection: {
    chosen: { hidden: number[]; alpha: number };
    candidates: { hidden: number[]; alpha: number; val_log_loss: number }[];
  };
  test_metrics: Record<string, ModelMetrics>;
  global_importance: { shap: Record<string, number>; lrp: Record<string, number> };
  explanation_quality: {
    rows_explained: number;
    method_agreement_spearman: Record<string, number>;
    lime_median_r2: number;
    counterfactual_found: number;
    counterfactual_valid: number;
    counterfactual_mean_features_changed: number;
    deletion_top3_shap: number;
    deletion_random3: number;
  };
  features: { name: string; label: string }[];
  limitations: string[];
}

// The learner report's Explainability section (backend app/xai): learner and admin views
export type UserReport = Json<"/api/v1/learners/me/report", "get", 200>;
export type ReportMatrixRow = UserReport["matrix"][number];
export type ReportPrediction = NonNullable<UserReport["decision"]>["predictions"][number];
export type RadarAxis = UserReport["radar"]["traits"][number];
export type LearnerListing = Json<"/api/v1/admin/learners", "get", 200>[number];
export type GlobalAttributions = Json<"/api/v1/admin/xai/global", "get", 200>;

// Learner state, graph, tests, admin
export type LearnerState = Json<"/api/v1/learners/me/state", "get", 200>;
export type StateUpdateView = Json<"/api/v1/learners/me/history", "get", 200>[number];
export type GraphResponse = Json<"/api/v1/graph", "get", 200>;
export type Concept = GraphResponse["concepts"][number];
export type ConceptEdge = GraphResponse["edges"][number];
export type TestPhase = "pretest" | "posttest";
export type TestOut = Json<"/api/v1/tests/{phase}", "get", 200>;
export type TestSubmitted = Json<"/api/v1/tests/{phase}", "post", 201>;
export type AdminMetricsResponse = Json<"/api/v1/admin/metrics", "get", 200>;
export type OpsStatus = Json<"/api/v1/ops/status", "get", 200>;

/** Earlier versions kept the token in localStorage: remove any that is left there. */
export function forgetLegacyToken(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  } catch {
    // storage unavailable: nothing was stored either
  }
}

/** Called when the server says the session is no longer valid, so the UI can return to login. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  let res: Response;
  try {
    res = await fetch(path, { ...options, headers, credentials: "same-origin" });
  } catch {
    throw new ApiException(0, {
      code: "NETWORK_ERROR",
      message: "Cannot reach the server. Check your connection and try again.",
    });
  }
  if (res.status === 204) return {} as T;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error: ApiError = data?.error || {
      code: "UNKNOWN_ERROR",
      message: res.statusText || "An unexpected error occurred",
    };
    // a wrong password is not a lost session
    if (res.status === 401 && !/^\/api\/v1\/auth\/(login|register)$/.test(path)) onUnauthorized?.();
    throw new ApiException(res.status, error);
  }
  return data as T;
}

const post = <T>(path: string, body: unknown = {}) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
const get = <T>(path: string) => request<T>(path, { method: "GET" });

export const api = {
  auth: {
    register: (payload: RegisterRequest) =>
      post<RegisterResponse>("/api/v1/auth/register", payload),
    login: (payload: LoginRequest) => post<LoginResponse>("/api/v1/auth/login", payload),
    consent: () => post<ConsentResponse>("/api/v1/auth/consent"),
    me: () => get<UserResponse>("/api/v1/auth/me"),
    logout: () => post<void>("/api/v1/auth/logout"),
    deleteMe: () => request<void>("/api/v1/me", { method: "DELETE" }),
  },

  onboarding: {
    getQuestionnaire: () => get<QuestionnaireItem[]>("/api/v1/onboarding/questionnaire"),
    submitQuestionnaire: (answers: Record<string, number>) =>
      post<StateDelta>("/api/v1/onboarding/questionnaire", { answers }),
  },

  session: {
    next: () => post<NextStepResponse>("/api/v1/session/next"),
  },

  attempts: {
    submit: (payload: AttemptIn) => post<AttemptResult>("/api/v1/attempts", payload),
  },

  explanations: {
    get: (id: string) => get<Explanation>(`/api/v1/explanations/${encodeURIComponent(id)}`),
    sendEvents: (id: string, events: ExplanationEvent[]) =>
      post<EventBatchResponse>(`/api/v1/explanations/${encodeURIComponent(id)}/events`, {
        events,
      }),
    close: (id: string) =>
      post<FeedbackOut>(`/api/v1/explanations/${encodeURIComponent(id)}/close`),
  },

  xai: {
    why: (recommendationId: string) =>
      get<RecommendationWhy>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/why`),
    belief: (subject: string) =>
      get<BeliefExplanation>(`/api/v1/learners/me/explain?subject=${encodeURIComponent(subject)}`),
    model: (recommendationId: string) =>
      get<ModelInsight>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/model`),
    modelCard: () => get<ModelCard>("/api/v1/model/card"),
  },

  learners: {
    getState: () => get<LearnerState>("/api/v1/learners/me/state"),
    getHistory: (limit = 50) => get<StateUpdateView[]>(`/api/v1/learners/me/history?limit=${limit}`),
    getReport: () => get<UserReport>("/api/v1/learners/me/report"),
  },

  graph: {
    get: () => get<GraphResponse>("/api/v1/graph"),
  },

  tests: {
    get: (phase: TestPhase) => get<TestOut>(`/api/v1/tests/${phase}`),
    submit: (phase: TestPhase, answers: Record<string, string>) =>
      post<TestSubmitted>(`/api/v1/tests/${phase}`, { answers }),
  },

  admin: {
    getMetrics: () => get<AdminMetricsResponse>("/api/v1/admin/metrics"),
    getOps: () => get<OpsStatus>("/api/v1/ops/status"),
    learners: () => get<LearnerListing[]>("/api/v1/admin/learners"),
    learnerReport: (learnerPseudonym: string) =>
      get<UserReport>(`/api/v1/admin/learners/${encodeURIComponent(learnerPseudonym)}/report`),
    globalXai: () => get<GlobalAttributions>("/api/v1/admin/xai/global"),
    downloadCsv: async (table: "users" | "assignments" | "attempts") => {
      const res = await fetch(`/api/v1/admin/export.csv?table=${table}`, { credentials: "same-origin" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new ApiException(res.status, data?.error || { code: "EXPORT_FAILED", message: "Export failed" });
      }
      return await res.blob();
    },
  },
};

/**
 * Send telemetry while the page is being closed: fetch with keepalive outlives the page and, being
 * same-origin, carries the session cookie.
 */
export function sendEventsOnUnload(explanationId: string, events: ExplanationEvent[]): void {
  if (events.length === 0) return;
  try {
    void fetch(`/api/v1/explanations/${encodeURIComponent(explanationId)}/events`, {
      method: "POST",
      keepalive: true,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: events.slice(0, 100) }),
    });
  } catch {
    // best effort: the events stay queued in localStorage and are retried next visit
  }
}

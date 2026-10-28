/**
 * The browser talks only to this app; this route forwards /api/v1/* to the API server.
 *
 * It exists so that the browser never holds the login token. On sign-in it takes the token out
 * of the API's answer and keeps it in an httpOnly, SameSite=Strict cookie that page scripts cannot
 * read, and it adds the token to every forwarded request. A script injected into a page could
 * still act while the page is open, but it cannot steal the session.
 *
 * Server-side settings (not compiled into the browser bundle):
 *   API_URL        where the API runs (falls back to NEXT_PUBLIC_API_URL, then localhost:8000)
 *   PROXY_SECRET   shared with the API, which then trusts the browser address sent in X-Client-IP
 *                  (otherwise every browser would share this server's address and its rate limit)
 */

const API_URL = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const COOKIE = "pcg_session";
const MAX_BODY_BYTES = 64 * 1024; // the API's own limit
const DAY_SECONDS = 24 * 60 * 60;
const REQUEST_HEADERS = ["content-type", "accept"];
const RESPONSE_HEADERS = ["content-type", "content-disposition", "retry-after"];
const SIGN_IN = new Set(["/api/v1/auth/login", "/api/v1/auth/register"]);
/** logging out and withdrawing end the session: POST /auth/logout, DELETE /me */
const SIGN_OUT = new Set(["/api/v1/auth/logout", "/api/v1/me"]);

function error(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status, headers: { "cache-control": "no-store" } });
}

function readCookie(request: Request, name: string): string | undefined {
  for (const part of (request.headers.get("cookie") ?? "").split(";")) {
    const [key, ...value] = part.trim().split("=");
    if (key === name) return value.join("=");
  }
  return undefined;
}

/** The session cookie: never readable by page scripts, never sent by other sites, API calls only. */
function sessionCookie(request: Request, value: string, seconds: number): string {
  const https = new URL(request.url).protocol === "https:" || request.headers.get("x-forwarded-proto") === "https";
  return `${COOKIE}=${value}; Path=/api; Max-Age=${seconds}; HttpOnly; SameSite=Strict${https ? "; Secure" : ""}`;
}

/** The browser's address, where a proxy we can trust says it. */
function clientIp(request: Request): string | null {
  const hops = (request.headers.get("x-forwarded-for") ?? "").split(",").map((h) => h.trim()).filter(Boolean);
  // Vercel replaces any X-Forwarded-For the browser sent with the browser's real address
  if (process.env.VERCEL) return request.headers.get("x-real-ip") ?? hops[0] ?? null;
  // another proxy in front of this server appends the address it saw
  if (process.env.TRUST_FORWARDED_FOR === "true") return hops.at(-1) ?? null;
  return null;
}

/** When the token runs out, so the cookie can go at the same time (a day if it cannot be read). */
function maxAge(token: string): number {
  try {
    const { exp } = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());
    return Math.max(0, Math.floor(exp - Date.now() / 1000));
  } catch {
    return DAY_SECONDS;
  }
}

async function forward(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;
  if (!path.startsWith("/api/v1/")) return error(404, "NOT_FOUND", "Not found");
  // the cookie is SameSite=Strict already; this also stops other sites' forms and scripts
  if (method !== "GET" && request.headers.get("sec-fetch-site") === "cross-site") {
    return error(403, "CROSS_SITE_REQUEST", "Requests from other sites are not allowed");
  }

  let body: ArrayBuffer | undefined;
  if (method !== "GET") {
    if (Number(request.headers.get("content-length") ?? 0) > MAX_BODY_BYTES) {
      return error(413, "PAYLOAD_TOO_LARGE", "Request body is too large");
    }
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_BODY_BYTES) return error(413, "PAYLOAD_TOO_LARGE", "Request body is too large");
  }

  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const token = readCookie(request, COOKIE);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const secret = process.env.PROXY_SECRET;
  const ip = clientIp(request);
  if (secret && ip) {
    headers.set("x-proxy-secret", secret);
    headers.set("x-client-ip", ip);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}${path}${url.search}`, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
  } catch {
    return error(502, "NETWORK_ERROR", "Cannot reach the server. Check your connection and try again.");
  }

  const out = new Headers({ "cache-control": "no-store" });
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }

  if (method === "POST" && SIGN_IN.has(path) && upstream.ok) {
    const { token: issued, ...rest } = await upstream.json();
    out.append("set-cookie", sessionCookie(request, issued, maxAge(issued)));
    return Response.json(rest, { status: upstream.status, headers: out });
  }

  const signedOut = method !== "GET" && SIGN_OUT.has(path) && (upstream.ok || upstream.status === 401);
  if (signedOut || (token && upstream.status === 401)) out.append("set-cookie", sessionCookie(request, "", 0));
  const empty = upstream.status === 204 || upstream.status === 304;
  return new Response(empty ? null : upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;

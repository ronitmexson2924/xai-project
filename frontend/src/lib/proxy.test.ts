// Unit tests for the API proxy route (src/app/api/[...path]/route.ts): node --test (npm run test:unit)
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

process.env.API_URL = "http://api.test";
process.env.PROXY_SECRET = "p".repeat(40);
const { GET, POST } = await import("../app/api/[...path]/route.ts");

type Sent = { url: string; init: RequestInit };
const realFetch = globalThis.fetch;
let sent: Sent[] = [];

function upstream(status: number, body: unknown, headers: Record<string, string> = {}) {
  sent = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    sent.push({ url, init });
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json", ...headers },
    });
  }) as typeof fetch;
}

function req(path: string, init: { method?: string; body?: string; headers?: Record<string, string> } = {}) {
  return new Request(`https://app.test${path}`, { method: init.method ?? "GET", body: init.body, headers: init.headers });
}

afterEach(() => {
  globalThis.fetch = realFetch;
  delete process.env.VERCEL;
});

const JWT = `x.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url")}.sig`;

test("signing in keeps the token in an httpOnly cookie and out of the page's hands", async () => {
  upstream(200, { token: JWT, user: { id: "u1" } });
  const res = await POST(req("/api/v1/auth/login", { method: "POST", body: "{}", headers: { "content-type": "application/json" } }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { user: { id: "u1" } });
  const cookie = res.headers.get("set-cookie") ?? "";
  assert.match(cookie, /^pcg_session=x\./);
  assert.match(cookie, /HttpOnly/i);
  assert.match(cookie, /SameSite=Strict/);
  assert.match(cookie, /Secure/i);
  assert.match(cookie, /Path=\/api/);
  assert.match(cookie, /Max-Age=(3[56]\d\d)/);
});

test("the cookie goes to the API as a bearer token", async () => {
  upstream(200, { ok: true });
  await GET(req("/api/v1/learners/me/state?x=1", { headers: { cookie: `pcg_session=${JWT}` } }));
  assert.equal(sent[0].url, "http://api.test/api/v1/learners/me/state?x=1");
  assert.equal(new Headers(sent[0].init.headers).get("authorization"), `Bearer ${JWT}`);
});

test("a rejected session or a log-out clears the cookie", async () => {
  upstream(401, { error: { code: "INVALID_TOKEN", message: "x" } });
  const expired = await GET(req("/api/v1/auth/me", { headers: { cookie: "pcg_session=old" } }));
  assert.equal(expired.status, 401);
  assert.match(expired.headers.get("set-cookie") ?? "", /^pcg_session=; Path=\/api; Max-Age=0/);
  upstream(204, null);
  const out = await POST(req("/api/v1/auth/logout", { method: "POST", headers: { cookie: "pcg_session=t" } }));
  assert.equal(out.status, 204);
  assert.match(out.headers.get("set-cookie") ?? "", /Max-Age=0/);
});

test("other sites cannot post through the proxy", async () => {
  upstream(200, {});
  const res = await POST(req("/api/v1/attempts", { method: "POST", body: "{}", headers: { "sec-fetch-site": "cross-site" } }));
  assert.equal(res.status, 403);
  assert.equal(sent.length, 0);
});

test("only the API's /api/v1 paths are forwarded, and big bodies stop here", async () => {
  upstream(200, {});
  assert.equal((await GET(req("/api/other"))).status, 404);
  const big = await POST(req("/api/v1/attempts", { method: "POST", body: "x".repeat(70 * 1024) }));
  assert.equal(big.status, 413);
  assert.equal(sent.length, 0);
});

test("the browser's address is passed on, with the secret, only where a proxy vouches for it", async () => {
  upstream(200, {});
  await GET(req("/api/v1/graph", { headers: { "x-forwarded-for": "6.6.6.6" } }));
  assert.equal(new Headers(sent[0].init.headers).get("x-client-ip"), null); // not behind a known proxy
  process.env.VERCEL = "1";
  upstream(200, {});
  await GET(req("/api/v1/graph", { headers: { "x-forwarded-for": "198.51.100.4" } }));
  const headers = new Headers(sent[0].init.headers);
  assert.equal(headers.get("x-client-ip"), "198.51.100.4");
  assert.equal(headers.get("x-proxy-secret"), "p".repeat(40));
});

test("an unreachable API gives the app's usual error shape", async () => {
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed");
  }) as typeof fetch;
  const res = await GET(req("/api/v1/graph"));
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error.code, "NETWORK_ERROR");
});

import { expect, test } from "@playwright/test";
import { API, consent, questionnaire, register, token, uniqueEmail } from "./helpers";

// What a curious or malicious participant would try from the browser.

test("pages that need an account send visitors to the login page", async ({ page }) => {
  for (const path of ["/session", "/onboarding", "/pretest"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login/);
  }
});

test("a tampered token is treated as logged out", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => localStorage.setItem("pcg_token", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0."));
  await page.goto("/session");
  await expect(page).toHaveURL(/\/login/);
});

test("markup in a display name is shown as text, never run", async ({ page }) => {
  let alerted = false;
  page.on("dialog", (d) => {
    alerted = true;
    void d.dismiss();
  });
  const name = `<img src=x onerror="alert(1)">`;
  await register(page, name, uniqueEmail("xss"));
  await page.goto("/");
  await expect(page.getByText(name).first()).toBeVisible();
  expect(alerted).toBe(false);
});

test("a learner cannot open the admin area or its API", async ({ page }) => {
  await register(page, "Not An Admin", uniqueEmail("noadmin"));
  await consent(page);
  await expect(page.getByRole("link", { name: /Admin/ })).toHaveCount(0);
  const r = await page.request.get(`${API}/admin/metrics`, {
    headers: { Authorization: `Bearer ${await token(page)}` },
  });
  expect(r.status()).toBe(403);
});

test("double-clicking submit records one answer", async ({ page }) => {
  await register(page, "Double Clicker", uniqueEmail("double"));
  await consent(page);
  await questionnaire(page);
  await page.goto("/session");
  await page.locator('button[role="radio"]').first().click();
  await page.getByRole("button", { name: /Submit Answer/i }).dblclick();
  await expect(page.getByRole("status").first()).toBeVisible();
  // (Next.js keeps an empty role="alert" route announcer on every page)
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveCount(0);
  const state = await page.request.get(`${API}/learners/me/state`, {
    headers: { Authorization: `Bearer ${await token(page)}` },
  });
  expect((await state.json()).total_attempts).toBe(1);
});

test("replaying an answer through the API is refused", async ({ page, request }) => {
  await register(page, "Replayer", uniqueEmail("replay"));
  await consent(page);
  await questionnaire(page);
  const h = { Authorization: `Bearer ${await token(page)}` };
  const step = await (await request.post(`${API}/session/next`, { headers: h })).json();
  const body = {
    item_id: step.item.id,
    response: step.item.options[0],
    latency_ms: 4000,
    recommendation_id: step.recommendation.id,
  };
  expect((await request.post(`${API}/attempts`, { headers: h, data: body })).status()).toBe(200);
  expect((await request.post(`${API}/attempts`, { headers: h, data: body })).status()).toBe(409);
});

test("guessing a password is cut off by the rate limit", async ({ request }) => {
  const email = uniqueEmail("guess");
  await request.post(`${API}/auth/register`, {
    data: { email, password: "the real passphrase", display_name: "Target" },
  });
  const codes: number[] = [];
  for (let i = 0; i < 12; i++) {
    const r = await request.post(`${API}/auth/login`, { data: { email, password: `guess-${i}-xxxx` } });
    codes.push(r.status());
  }
  expect(codes).toContain(429);
});

test("deleting the account signs out everywhere", async ({ page, request }) => {
  await register(page, "Leaver", uniqueEmail("leaver"));
  await consent(page);
  const h = { Authorization: `Bearer ${await token(page)}` };
  expect((await request.delete(`${API}/me`, { headers: h })).status()).toBe(204);
  expect((await request.get(`${API}/auth/me`, { headers: h })).status()).toBe(401);
  await page.goto("/session");
  await expect(page).toHaveURL(/\/login/);
});

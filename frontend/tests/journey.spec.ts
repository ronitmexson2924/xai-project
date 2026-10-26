import { expect, test } from "@playwright/test";
import {
  ADMIN,
  API,
  answerCurrentQuestion,
  answerQuestionnaire,
  consent,
  login,
  register,
  token,
  uniqueEmail,
} from "./helpers";

test.describe("a learner's whole study, in the browser", () => {
  test("landing → sign up → consent → questionnaire → dashboard → pre-test → learn with XAI → post-test", async ({
    page,
    request,
  }) => {
    const email = uniqueEmail("journey");
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByRole("link", { name: "Get started" }).click();
    await expect(page).toHaveURL(/\/signup/);
    await register(page, email, "Journey Learner");
    await consent(page);

    // the study track must never be shown to participants (blinding)
    for (const arm of ["closed_loop", "static_personalized", "generic"]) {
      await expect(page.getByText(arm)).toHaveCount(0);
    }

    await answerQuestionnaire(page);
    await expect(page.getByRole("heading", { name: /Good (morning|afternoon|evening), Journey/ })).toBeVisible();
    await page.getByRole("link", { name: /Start the pre-test/ }).click();
    await expect(page).toHaveURL(/\/tests\/pretest/);
    await expect(page.getByText(/questions\. Answer what you can/)).toBeVisible();
    await page.locator('input[type="radio"]').first().check();
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page.getByText(/question\(s\) unanswered/)).toBeVisible(); // warned, not lost
    await page.getByRole("button", { name: "Submit anyway" }).click();
    await expect(page.getByTestId("test-done")).toBeVisible();
    await expect(page.getByTestId("test-done")).not.toContainText(/score|correct|\d+\s*\/\s*\d+/i);

    await page.getByRole("link", { name: /Start learning/ }).click();
    await expect(page).toHaveURL(/\/session/);

    // placement questions: the question comes first and the explanation only after the answer
    await expect(page.getByTestId("placement-note")).toBeVisible();
    await expect(page.getByTestId("explanation-card")).toHaveCount(0);
    await answerCurrentQuestion(page);
    await expect(page.getByTestId("explanation-card")).toBeVisible();
    await expect(page.getByTestId("answered-count")).toContainText("1");
    // the worked example is a code block, not code flattened into sentences
    await expect(page.getByTestId("explanation-card").locator("pre code").first()).toBeVisible();

    // "Why this?" shows the stored rationale (XAI E1-E3)
    await page.getByRole("button", { name: /Why this\?/ }).click();
    await expect(page.getByTestId("why-summary")).toContainText(/placement question/i);

    // finish the placement phase
    for (let i = 2; i <= 8; i++) {
      await page.getByRole("button", { name: /Continue/ }).click();
      await answerCurrentQuestion(page);
      await expect(page.getByTestId("answered-count")).toContainText(String(i));
    }

    // practice: explanation first, its question is the micro-check
    await page.getByRole("button", { name: /Continue/ }).click();
    await expect(page.getByTestId("explanation-card")).toBeVisible();
    await expect(page.getByTestId("placement-note")).toHaveCount(0);
    await page.getByRole("button", { name: /Why this\?/ }).click();
    await expect(page.getByTestId("why-summary")).not.toBeEmpty();
    await answerCurrentQuestion(page);

    // the answer's effects reached the learner model and its audit log
    const auth = { Authorization: `Bearer ${await token(page)}` };
    const state = await (await request.get(`${API}/learners/me/state`, { headers: auth })).json();
    expect(state.total_attempts).toBe(9);
    const history = await (await request.get(`${API}/learners/me/history`, { headers: auth })).json();
    expect(history.some((h: { source: string }) => h.source === "explanation_feedback")).toBe(true);

    // open learner model (E4)
    await page.goto("/dashboard");
    await expect(page.getByTestId("trait-card")).toBeVisible();
    await expect(page.getByTestId("belief-abstraction_preference")).toBeVisible();

    // post-test, then the tests page shows both submitted
    await page.goto("/tests/posttest");
    await page.locator('input[type="radio"]').first().check();
    await page.getByRole("button", { name: "Submit" }).click();
    await page.getByRole("button", { name: "Submit anyway" }).click();
    await expect(page.getByTestId("test-done")).toBeVisible();
    await page.goto("/tests");
    await expect(page.getByText("Submitted")).toHaveCount(2);

    // a returning learner goes straight to the dashboard, with no questionnaire
    const oldToken = await token(page);
    await page.getByTestId("nav-user").click();
    await page.getByRole("menuitem", { name: "Log out" }).click();
    await expect(page).toHaveURL(/:\d+\/$/);
    // logging out revokes the token on the server too
    const me = await request.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${oldToken}` } });
    expect(me.status()).toBe(401);
    await login(page, email);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("next-step")).toContainText("Continue learning");
  });

  test("an admin sees measured metrics and can export pseudonymised data", async ({ page }) => {
    await login(page, ADMIN.email, ADMIN.password);
    await expect(page).not.toHaveURL(/\/login/); // logged in (admins skip the study consent)
    await page.goto("/admin");
    await expect(page.getByText(/explanation latency/).first()).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download assignments.csv" }).click();
    const csv = await (await download).path();
    expect(csv).toBeTruthy();
  });
});

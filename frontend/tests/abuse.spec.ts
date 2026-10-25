import { expect, test } from "@playwright/test";
import {
  API,
  PASSWORD,
  answerCurrentQuestion,
  answerQuestionnaire,
  consent,
  login,
  register,
  token,
  uniqueEmail,
} from "./helpers";

test.describe("what a curious or hostile user tries in the browser", () => {
  test("protected pages send visitors to login, then new learners to onboarding", async ({ page }) => {
    for (const path of ["/session", "/dashboard", "/tests/pretest", "/admin", "/account", "/onboarding"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login/);
    }
    await register(page, uniqueEmail("guard"));
    await expect(page).toHaveURL(/\/onboarding/);
    for (const path of ["/session", "/dashboard", "/tests/pretest"]) {
      await page.goto(path); // no learning before consent and the questionnaire
      await expect(page).toHaveURL(/\/onboarding/);
    }
    await consent(page);
    await page.goto("/dashboard"); // consent alone is not enough either
    await expect(page).toHaveURL(/\/onboarding/);
    await expect(page.getByText(/Question 1 of/)).toBeVisible(); // resumes at the questionnaire
  });

  test("a learner cannot open the admin page", async ({ page }) => {
    await register(page, uniqueEmail("not-admin"));
    await consent(page);
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin/);
    await expect(page.getByText(/Download users\.csv/)).toHaveCount(0);
  });

  test("a script in the display name is shown as text, never run", async ({ page }) => {
    let dialog = false;
    page.on("dialog", async (d) => {
      dialog = true;
      await d.dismiss();
    });
    await register(page, uniqueEmail("xss"), "<img src=x onerror=alert(1)><script>alert(2)</script>");
    await consent(page);
    await answerQuestionnaire(page);
    await page.getByTestId("nav-user").click();
    await expect(page.getByRole("menu")).toContainText("<img src=x onerror=alert(1)>");
    expect(dialog).toBe(false);
  });

  test("duplicate sign-up and wrong passwords give clear messages; guessing gets locked", async ({ page }) => {
    const email = uniqueEmail("dup");
    await register(page, email);
    await expect(page).toHaveURL(/\/onboarding/);
    await page.evaluate(() => localStorage.clear());

    await register(page, email);
    await expect(page.getByText("Email is already registered")).toBeVisible();

    for (let i = 0; i < 5; i++) {
      await login(page, email, "wrong-password-1");
      await expect(page.getByText("Incorrect email or password")).toBeVisible();
    }
    await login(page, email, PASSWORD); // even the right password is refused while locked
    await expect(page.getByText(/Too many failed logins/)).toBeVisible();
  });

  test("a tampered token in storage logs the user out instead of breaking the page", async ({ page }) => {
    await register(page, uniqueEmail("tamper"));
    await consent(page);
    await page.evaluate(() => {
      const t = localStorage.getItem("pcg_token") ?? "";
      localStorage.setItem("pcg_token", t.slice(0, -4) + "AAAA");
    });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("double-clicking submit records one answer; reloading shows the same question", async ({
    page,
    request,
  }) => {
    await register(page, uniqueEmail("double"));
    await consent(page);
    await answerQuestionnaire(page);
    await page.goto("/session");
    const stem = await page.locator("main").innerText();
    await page.reload(); // refreshing must not skip the question
    await expect(page.locator("main")).toContainText(stem.split("\n").find((l) => l.length > 20) ?? "");

    const text = page.getByLabel("Your answer");
    if (await text.isVisible().catch(() => false)) await text.fill("x");
    else await page.locator('[aria-label="Question options"] button[role="radio"]').first().click();
    const submit = page.getByRole("button", { name: "Submit answer" });
    await submit.dblclick();
    await expect(page.getByTestId("attempt-result")).toBeVisible();

    const auth = { Authorization: `Bearer ${await token(page)}` };
    const state = await (await request.get(`${API}/learners/me/state`, { headers: auth })).json();
    expect(state.total_attempts).toBe(1);
  });

  test("the pre-test can be taken only once, even by going back", async ({ page }) => {
    await register(page, uniqueEmail("retake"));
    await consent(page);
    await answerQuestionnaire(page);
    await page.goto("/tests/pretest");
    await page.locator('input[type="radio"]').first().check();
    await page.getByRole("button", { name: "Submit" }).click();
    await page.getByRole("button", { name: "Submit anyway" }).click();
    await expect(page.getByTestId("test-done")).toBeVisible();
    await page.goBack();
    await page.goto("/tests/pretest");
    await expect(page.getByTestId("test-done")).toBeVisible();
    await expect(page.getByRole("button", { name: "Submit" })).toHaveCount(0);
  });

  test("answers are never in the page before the learner answers", async ({ page }) => {
    await register(page, uniqueEmail("peek"));
    await consent(page);
    await answerQuestionnaire(page);
    const responses: string[] = [];
    page.on("response", async (r) => {
      if (r.url().includes("/session/next") || r.url().includes("/tests/")) {
        responses.push(await r.text().catch(() => ""));
      }
    });
    await page.goto("/session");
    await expect(page.locator("main")).toContainText(/Submit answer|Continue/);
    await page.goto("/tests/pretest");
    await expect(page.getByRole("button", { name: "Submit" })).toBeVisible();
    expect(responses.length).toBeGreaterThan(0);
    for (const body of responses) expect(body).not.toContain('"answer"');
  });

  test("withdrawing deletes access for good", async ({ page }) => {
    const email = uniqueEmail("withdraw");
    await register(page, email);
    await consent(page);
    await answerQuestionnaire(page);
    await page.getByTestId("nav-user").click();
    await page.getByRole("menuitem", { name: /Account/ }).click();
    await expect(page).toHaveURL(/\/account/);
    await page.getByRole("button", { name: "Withdraw" }).click();
    await page.getByRole("button", { name: /Yes, withdraw/ }).click();
    await expect(page).toHaveURL(/:\d+\/$/);
    await login(page, email);
    await expect(page.getByText("Incorrect email or password")).toBeVisible();
  });

  test("the app survives the API being unreachable", async ({ page }) => {
    await register(page, uniqueEmail("offline"));
    await consent(page);
    await answerQuestionnaire(page);
    await page.route("**/api/v1/session/next", (route) => route.abort());
    await page.goto("/session");
    await expect(page.getByRole("alert").filter({ hasText: /Cannot reach the server/ })).toBeVisible();
    await page.unroute("**/api/v1/session/next");
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(page.getByRole("button", { name: "Submit answer" })).toBeVisible();
    await answerCurrentQuestion(page);
  });
});

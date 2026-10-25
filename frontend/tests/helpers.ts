import { expect, Page } from "@playwright/test";

export const API = "http://localhost:8000/api/v1";
export const PASSWORD = "Learner-pass-42";
export const ADMIN = { email: "e2e-admin@example.com", password: "E2e-admin-pass-1" };

export function uniqueEmail(tag: string): string {
  return `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function register(page: Page, email: string, name = "E2E Learner", password = PASSWORD) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Register here" }).click();
  await page.getByPlaceholder("e.g. Ada Lovelace").fill(name);
  await page.getByPlaceholder("you@domain.edu").fill(email);
  await page.getByPlaceholder("••••••••").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
}

export async function login(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByPlaceholder("you@domain.edu").fill(email);
  await page.getByPlaceholder("••••••••").fill(password);
  await page.locator("form").getByRole("button", { name: "Sign In" }).click();
}

export async function consent(page: Page) {
  await expect(page).toHaveURL(/\/consent/);
  await page.getByRole("button", { name: /Give Research Consent/i }).click();
  await expect(page).toHaveURL(/\/onboarding/);
}

export async function answerQuestionnaire(page: Page) {
  await expect(page.getByText("How much do you agree?")).toBeVisible();
  for (;;) {
    await page.locator('button[role="radio"]').nth(3).click();
    const next = page.getByRole("button", { name: /Next Question/ });
    if (await next.isVisible()) {
      await next.click();
    } else {
      break;
    }
  }
  await page.getByRole("button", { name: "Finish questionnaire" }).click();
  await expect(page.getByRole("heading", { name: "Next: a short pre-test" })).toBeVisible();
}

/** Answer whatever the session shows: pick the first option or type a short answer. */
export async function answerCurrentQuestion(page: Page) {
  const text = page.getByLabel("Your answer");
  if (await text.isVisible().catch(() => false)) {
    await text.fill("my answer");
  } else {
    await page.locator('[role="radiogroup"][aria-label="Question options"] button[role="radio"]').first().click();
  }
  await page.getByRole("button", { name: "Submit Answer" }).click();
  await expect(page.getByTestId("attempt-result")).toBeVisible();
}

export async function token(page: Page): Promise<string> {
  return (await page.evaluate(() => localStorage.getItem("pcg_token"))) ?? "";
}

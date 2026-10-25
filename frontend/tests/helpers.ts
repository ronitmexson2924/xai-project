import { expect, Page } from "@playwright/test";

export const API = "http://localhost:8000/api/v1";
export const PASSWORD = "Learner-pass-42";
export const ADMIN = { email: "e2e-admin@example.com", password: "E2e-admin-pass-1" };

export function uniqueEmail(tag: string): string {
  return `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function register(page: Page, email: string, name = "E2E Learner", password = PASSWORD) {
  await page.goto("/signup");
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
}

export async function login(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.locator("form").getByRole("button", { name: "Log in" }).click();
}

/** The first onboarding step: read the study information and agree. */
export async function consent(page: Page) {
  await expect(page).toHaveURL(/\/onboarding/);
  const agree = page.getByRole("button", { name: "Agree and continue" });
  await expect(agree).toBeDisabled(); // nothing is agreed by default
  await page.getByLabel(/I have read this and agree/).check();
  await agree.click();
  await expect(page.getByText(/Question 1 of \d+/)).toBeVisible();
}

/** Answer every questionnaire item ("Agree"), finish, and land on the dashboard. */
export async function answerQuestionnaire(page: Page) {
  const counter = page.getByText(/Question \d+ of \d+/);
  await expect(counter).toBeVisible();
  const total = Number((await counter.innerText()).match(/of (\d+)/)![1]);
  for (let n = 1; n <= total; n++) {
    await expect(page.getByText(`Question ${n} of ${total}`)).toBeVisible();
    await page
      .getByRole("radiogroup", { name: "How much do you agree?" })
      .getByRole("radio", { name: "Agree", exact: true })
      .click();
  }
  await page.getByRole("button", { name: "Finish" }).click();
  await page.getByRole("button", { name: /Go to your dashboard/ }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByTestId("next-step")).toBeVisible();
}

/** Answer whatever the session shows: pick the first option or type a short answer. */
export async function answerCurrentQuestion(page: Page) {
  const text = page.getByLabel("Your answer");
  if (await text.isVisible().catch(() => false)) {
    await text.fill("my answer");
  } else {
    await page.locator('[role="radiogroup"][aria-label="Question options"] button[role="radio"]').first().click();
  }
  await page.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByTestId("attempt-result")).toBeVisible();
}

export async function token(page: Page): Promise<string> {
  return (await page.evaluate(() => localStorage.getItem("pcg_token"))) ?? "";
}

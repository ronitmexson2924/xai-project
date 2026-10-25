import { expect, Page } from "@playwright/test";

export const API = "http://localhost:8000/api/v1";

export function uniqueEmail(tag: string): string {
  return `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function register(page: Page, name: string, email: string, password = "a long passphrase 1") {
  await page.goto("/login");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.fill('input[placeholder="e.g. Ada Lovelace"]', name);
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL(/\/consent/);
}

export async function consent(page: Page) {
  await page.getByRole("button", { name: /Give Research Consent/i }).click();
  await expect(page).toHaveURL(/\/onboarding/);
}

export async function questionnaire(page: Page) {
  // keyboard path: 1-5 picks a rating (the page's documented shortcut)
  const next = page.getByRole("button", { name: /Next Question/i });
  await expect(next).toBeVisible();
  while (await next.isVisible()) {
    await page.keyboard.press("3");
    await next.click();
  }
  await page.keyboard.press("3");
  await page.getByRole("button", { name: /Complete & Begin/i }).click();
  await expect(page.getByRole("heading", { name: /starting quiz/i })).toBeVisible();
}

export async function token(page: Page): Promise<string> {
  return (await page.evaluate(() => localStorage.getItem("pcg_token"))) || "";
}

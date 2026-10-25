import { expect, test } from "@playwright/test";
import { API, consent, questionnaire, register, token, uniqueEmail } from "./helpers";

// A new learner goes through everything a participant does (tasks/mit.md M4 acceptance, plus the
// XAI panels from M10), against the real API and database.
test("a new learner completes onboarding, the starting quiz and three practice steps", async ({ page }) => {
  const dialogs: string[] = [];
  page.on("dialog", (d) => {
    dialogs.push(d.message());
    void d.dismiss();
  });

  await register(page, "Journey Learner", uniqueEmail("journey"));
  // participants are not told their experiment arm
  await expect(page.getByText(/closed_loop|static_personalized|generic/)).toHaveCount(0);
  await consent(page);
  await questionnaire(page);

  await page.getByRole("link", { name: /Start the quiz/i }).click();
  await expect(page).toHaveURL(/\/pretest/);
  for (let i = 0; i < 15; i++) {
    await expect(page.getByText(`Question ${i + 1} of 15`)).toBeVisible();
    await page.locator('button[role="radio"]').first().click();
    await page.getByRole("button", { name: /Submit Answer/i }).click();
  }
  await expect(page.getByText(/that is the whole quiz/i)).toBeVisible();
  await page.getByRole("link", { name: /Start practising/i }).click();
  await expect(page).toHaveURL(/\/session/);

  for (let step = 1; step <= 3; step++) {
    await expect(page.locator('button[role="radio"]').first()).toBeVisible();
    await page.locator('button[role="radio"]').first().click();
    await page.getByRole("button", { name: /Submit Answer/i }).click();
    await expect(page.getByRole("status").first()).toBeVisible();

    // "Why this?" shows the stored rationale
    await page.getByRole("button", { name: /Why this\?/ }).click();
    await expect(page.getByText("Loading…")).toHaveCount(0);
    await expect(page.getByText(/could not be loaded/)).toHaveCount(0);

    const check = page.getByRole("button", { name: /Check my understanding/i });
    if (await check.isVisible()) {
      await check.click();
      await page.locator('button[role="radio"]:not([disabled])').first().click();
      await page.getByRole("button", { name: /Submit Answer/i }).click();
      await page.getByRole("button", { name: /Next step/i }).click();
    } else {
      await page.getByRole("button", { name: /Continue/i }).click();
    }
  }

  // the server saw all of it
  const state = await page.request.get(`${API}/learners/me/state`, {
    headers: { Authorization: `Bearer ${await token(page)}` },
  });
  expect((await state.json()).total_attempts).toBeGreaterThanOrEqual(3);

  // open learner model
  await page.goto("/dashboard");
  await expect(page.getByText(/Plain-Language Learning Profile/i)).toBeVisible();
  await page.getByRole("button", { name: /Why we think this/i }).first().click();
  await expect(page.getByText(/confidence/).first()).toBeVisible();

  expect(dialogs).toEqual([]);
});

test("reloading the page mid-step shows the same question, not a new one", async ({ page }) => {
  await register(page, "Reload Learner", uniqueEmail("reload"));
  await consent(page);
  await questionnaire(page);
  await page.goto("/session");
  await expect(page.locator('button[role="radio"]').first()).toBeVisible();
  const before = await page.locator('div[role="radiogroup"]').innerText();
  await page.reload();
  await expect(page.locator('button[role="radio"]').first()).toBeVisible();
  expect(await page.locator('div[role="radiogroup"]').innerText()).toBe(before);
});

import { test, expect } from "@playwright/test";

test.describe("Learning UI End-to-End Smoke Test", () => {
  test("new user completes onboarding and 3 consecutive items", async ({ page }) => {
    const timestamp = Date.now();
    const testEmail = `smoke_learner_${timestamp}@example.com`;
    const testPassword = "Password123!";
    const testName = `Learner ${timestamp}`;

    // 1. Visit Login / Register page
    await page.goto("/login");
    await expect(page).toHaveTitle(/PCG Engine/i);

    // Switch to Register mode
    await page.getByRole("button", { name: "Register", exact: true }).click();

    // Fill registration form
    await page.fill('input[placeholder="e.g. Ada Lovelace"]', testName);
    await page.fill('input[type="email"]', testEmail);
    await page.fill('input[type="password"]', testPassword);
    await page.getByRole("button", { name: "Create Account" }).click();

    // 2. Consent Screen
    await expect(page).toHaveURL(/.*\/consent/);
    await expect(page.getByRole("heading", { name: /Informed Research Consent/i })).toBeVisible();

    // Click Consent Button
    await page.getByRole("button", { name: /I Understand & Give Research Consent/i }).click();

    // 3. Onboarding Questionnaire Screen
    await expect(page).toHaveURL(/.*\/onboarding/);
    await expect(page.getByRole("heading", { name: /Learning Preference Questionnaire/i })).toBeVisible();

    // Answer all questionnaire items until final submission
    while (await page.getByRole("button", { name: /Next Question →/i }).isVisible()) {
      const likertRadios = page.locator('button[role="radio"]');
      await expect(likertRadios.nth(3)).toBeVisible();
      await likertRadios.nth(3).click();
      await page.getByRole("button", { name: /Next Question →/i }).click();
    }

    // Answer the final question
    const finalRadios = page.locator('button[role="radio"]');
    await expect(finalRadios.nth(3)).toBeVisible();
    await finalRadios.nth(3).click();

    // Submit questionnaire
    const submitBtn = page.getByRole("button", { name: /Complete & Begin Diagnostic/i });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // 4. Diagnostic Intro Screen
    await expect(page.getByRole("heading", { name: /Next: Diagnostic Calibration/i })).toBeVisible();
    await page.getByRole("link", { name: /Start Diagnostic Session →/i }).click();

    // 5. Interactive Learning Session Loop
    await expect(page).toHaveURL(/.*\/session/);

    // Answer 3 items sequentially
    for (let itemIdx = 1; itemIdx <= 3; itemIdx++) {
      // Wait for question options to be visible
      const optionButtons = page.locator('button[role="radio"]');
      await expect(optionButtons.first()).toBeVisible({ timeout: 15000 });

      // Select first MCQ option
      await optionButtons.first().click();

      // Submit answer
      const submitAnswerBtn = page.getByRole("button", { name: /Submit Answer/i });
      await expect(submitAnswerBtn).toBeEnabled();
      await submitAnswerBtn.click();

      // Verify feedback banner appears
      await expect(page.locator("text=/Correct! Well done|Not quite right/i")).toBeVisible({
        timeout: 10000,
      });

      // Verify reasons panel is visible
      await expect(page.locator("text=/Why this recommendation?/i")).toBeVisible();

      // Verify concept explanation card is rendered
      await expect(page.locator("text=/Concept Explanation:/i")).toBeVisible();

      // Advance to next concept / item
      if (itemIdx < 3) {
        const nextConceptBtn = page.getByRole("button", { name: /Continue to Next Concept/i });
        await expect(nextConceptBtn).toBeVisible();
        await nextConceptBtn.click();
      }
    }

    // Verify counter shows 3 completed items
    await expect(page.locator("text=/Completed in Session: 3/i")).toBeVisible();
  });
});

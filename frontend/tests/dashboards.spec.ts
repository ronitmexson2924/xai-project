import { test, expect } from "@playwright/test";

test.describe("M6: Open Learner Model and Admin Dashboards", () => {
  test("Open Learner Model dashboard renders for Novice demo learner", async ({ page }) => {
    // 1. Log in as Ada Lovelace (Novice)
    await page.goto("/login");
    await page.fill('input[type="email"]', "novice@example.com");
    await page.fill('input[type="password"]', "Demo1234!");
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/.*\/(session)?$/);

    // 2. Navigate to Open Learner Model Dashboard
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /Knowledge Graph & Trait Model/i })).toBeVisible();
    await expect(page.getByText(/Open Learner Model/i).first()).toBeVisible();

    // 3. Verify Overview Stats
    await expect(page.getByText(/Concepts Mastered/i)).toBeVisible();
    await expect(page.getByText(/In Progress/i)).toBeVisible();
    await expect(page.getByText("Practice Attempts", { exact: true })).toBeVisible();
    await expect(page.getByText(/Logged Provenance Events/i)).toBeVisible();

    // 4. Verify React Flow Concept Graph
    const flowContainer = page.locator(".react-flow");
    await expect(flowContainer).toBeVisible();

    // Verify concept nodes rendered
    const conceptNodes = page.locator(".react-flow__node");
    await expect(conceptNodes.first()).toBeVisible();
    const nodeCount = await conceptNodes.count();
    expect(nodeCount).toBeGreaterThan(10);

    // 5. Test clicking a concept node to open Concept Detail Modal
    await conceptNodes.first().click();
    await expect(page.getByRole("button", { name: "Close details" })).toBeVisible();
    await expect(page.getByText(/BKT Mastery/i)).toBeVisible();
    await expect(page.getByText("Definition", { exact: true })).toBeVisible();

    // Close modal
    await page.getByRole("button", { name: "Close details" }).click();

    // 6. Verify Plain-Language Traits Profile
    await expect(page.getByText(/Plain-Language Learning Profile/i)).toBeVisible();
    await expect(page.getByText(/Learning Structure/i)).toBeVisible();
    await expect(page.getByText(/Explanation Density/i)).toBeVisible();

    // 7. Verify "Why We Think This" Audit Trail
    await expect(page.getByText(/Why We Think This/i)).toBeVisible();
    await expect(page.getByText(/Intake Questionnaire/i).first()).toBeVisible();
  });

  test("Dashboards render for Intermediate and Advanced demo learners", async ({ page }) => {
    // 1. Log in as Intermediate learner
    await page.goto("/login");
    await page.fill('input[type="email"]', "intermediate@example.com");
    await page.fill('input[type="password"]', "Demo1234!");
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/.*\/(session)?$/);

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /Knowledge Graph & Trait Model/i })).toBeVisible();
    await expect(page.locator(".react-flow")).toBeVisible();

    // 2. Switch to Advanced learner via Navbar demo switcher
    await page.getByRole("button", { name: "Advanced", exact: true }).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Knowledge Graph & Trait Model/i })).toBeVisible();
    await expect(page.locator(".react-flow")).toBeVisible();
  });

  test("Admin dashboard renders metrics, balancing, SLAs, and CSV exports", async ({ page }) => {
    // 1. Log in as demo user
    await page.goto("/login");
    await page.fill('input[type="email"]', "advanced@example.com");
    await page.fill('input[type="password"]', "Demo1234!");
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/.*\/(session)?$/);

    // 2. Visit /admin
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /Study Analytics & Telemetry/i })).toBeVisible();

    // 3. Verify SLA latency metrics
    await expect(page.getByText("p50 Latency", { exact: true })).toBeVisible();
    await expect(page.getByText("p95 Latency", { exact: true })).toBeVisible();
    await expect(page.getByText(/PASS \(<100ms\)/i).first()).toBeVisible();

    // 4. Verify Study Arm Balancing
    await expect(page.getByText(/Participant Balancing Across Study Arms/i)).toBeVisible();
    await expect(page.getByText(/Closed Loop \(Adaptive\)/i)).toBeVisible();
    await expect(page.getByText(/Static Personalized/i)).toBeVisible();
    await expect(page.getByText(/Generic Control/i)).toBeVisible();

    // 5. Verify Telemetry Breakdown
    await expect(page.getByText(/Explanation Generation Source Mix/i)).toBeVisible();
    await expect(page.getByText(/Explanation Clarity Distribution/i)).toBeVisible();

    // 6. Verify CSV Export Buttons
    await expect(page.getByRole("button", { name: /Download users.csv/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Download assignments.csv/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Download attempts.csv/i })).toBeVisible();
  });
});

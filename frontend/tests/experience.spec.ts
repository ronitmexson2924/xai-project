import { expect, Page, test } from "@playwright/test";
import { answerCurrentQuestion, answerQuestionnaire, consent, register, uniqueEmail } from "./helpers";

/** Basic checks a screen reader or keyboard user depends on, run on every page of the flow. */
async function expectAccessible(page: Page) {
  // Next keeps visited routes mounted but hidden (React <Activity>), so only visible elements count
  await expect(page.locator("h1:visible")).toHaveCount(1); // also waits for a client-side navigation to settle
  const problems = await page.evaluate(() => {
    const out: string[] = [];
    const visible = (sel: string) => [...document.querySelectorAll(sel)].filter((el) => el.checkVisibility());
    const named = (el: Element) =>
      Boolean(
        el.getAttribute("aria-label")?.trim() ||
          el.getAttribute("aria-labelledby") ||
          el.getAttribute("title")?.trim() ||
          (el as HTMLElement).innerText?.trim()
      );
    if (!document.documentElement.lang) out.push("<html> has no lang");
    visible("button, a[href], [role=button], [role=radio], [role=menuitem]").forEach((el) => {
      if (!named(el)) out.push(`unnamed ${el.tagName.toLowerCase()}: ${el.outerHTML.slice(0, 80)}`);
    });
    visible("input:not([type=hidden]), textarea, select").forEach((el) => {
      const id = el.getAttribute("id");
      const labelled =
        el.getAttribute("aria-label") || el.closest("label") || (id && document.querySelector(`label[for="${id}"]`));
      if (!labelled) out.push(`unlabelled input: ${el.outerHTML.slice(0, 80)}`);
    });
    visible("img").forEach((el) => {
      if (!el.hasAttribute("alt")) out.push(`img without alt: ${el.outerHTML.slice(0, 80)}`);
    });
    if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push("page scrolls horizontally");
    return out;
  });
  expect(problems).toEqual([]);
}

test.describe("the first-run experience", () => {
  test("landing page explains the product and leads to sign up or log in", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Concept/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectAccessible(page);
    await page.getByRole("link", { name: "I have an account" }).click();
    await expect(page).toHaveURL(/\/login/);
    await expectAccessible(page);
    await page.getByRole("link", { name: "Create an account" }).click();
    await expect(page).toHaveURL(/\/signup/);
    await expectAccessible(page);
  });

  test("sign-up validates input before it reaches the server", async ({ page }) => {
    await page.goto("/signup");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Tell us what to call you")).toBeVisible();
    await page.getByLabel("Name", { exact: true }).fill("Short Pass");
    await page.getByLabel("Email", { exact: true }).fill("not-an-email");
    await page.getByLabel("Password", { exact: true }).fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/signup/);
    await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("aria-invalid", "true");
  });

  test("onboarding works with the keyboard alone and every step is accessible", async ({ page }) => {
    await register(page, uniqueEmail("keys"), "Keyboard Learner");
    await expect(page).toHaveURL(/\/onboarding/);
    await expectAccessible(page);
    await consent(page);
    await expectAccessible(page);

    const counter = page.getByText(/Question \d+ of \d+/);
    const total = Number((await counter.innerText()).match(/of (\d+)/)![1]);
    await page.keyboard.press("4");
    await expect(page.getByText(`Question 2 of ${total}`)).toBeVisible(); // auto-advances
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByText(`Question 1 of ${total}`)).toBeVisible();
    await expect(page.getByRole("radio", { name: "Agree", exact: true })).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("ArrowRight");
    for (let n = 2; n <= total; n++) {
      await expect(page.getByText(`Question ${n} of ${total}`)).toBeVisible();
      await page.keyboard.press(String((n % 5) + 1));
    }
    await page.getByRole("button", { name: "Finish" }).click();
    await expect(page.getByRole("heading", { name: /all set, Keyboard/ })).toBeVisible();
    await page.getByRole("button", { name: /Go to your dashboard/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expectAccessible(page);

    // a finished learner who opens onboarding again is sent back to the dashboard
    await page.goto("/onboarding");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("the dashboard's concept map explains each estimate", async ({ page }) => {
    await register(page, uniqueEmail("map"));
    await consent(page);
    await answerQuestionnaire(page);
    const tile = page.getByRole("button", { name: /Not started/ }).first();
    await tile.click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Why we think this")).toBeVisible();
    await expect(drawer.getByText("Key idea")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(drawer).toHaveCount(0);
  });
});

test("a concept-card flowchart is drawn as a diagram, not shown as source", async ({ page }) => {
  await register(page, uniqueEmail("diagram"));
  await consent(page);
  await answerQuestionnaire(page);
  // the diagrams only appear for some concepts and styles, so put one into the next explanation
  await page.route("**/api/v1/session/next", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.explanation.body_markdown +=
      '\n\n```mermaid\nflowchart TD\n  A["fact(2)"] --> B["2 * fact(1)"] --> C["1 * fact(0)"]\n```';
    await route.fulfill({ response, json: body });
  });
  await page.goto("/session");
  await answerCurrentQuestion(page); // placement: the explanation follows the answer
  const diagram = page.getByTestId("diagram");
  await expect(diagram).toBeVisible();
  await expect(diagram.getByText("2 * fact(1)")).toBeVisible();
  await expect(diagram.getByRole("img")).toHaveAttribute("aria-label", /fact\(2\) leads to 2 \* fact\(1\)/);
  await expect(page.getByText("flowchart TD")).toHaveCount(0);
});

test.describe("dark mode and small screens", () => {
  test.use({ colorScheme: "dark", viewport: { width: 375, height: 740 } });

  test("pages follow the system theme and fit a phone screen", async ({ page }) => {
    await page.goto("/");
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toBe("rgb(9, 9, 11)");
    await expectAccessible(page);

    await register(page, uniqueEmail("phone"));
    await consent(page);
    await answerQuestionnaire(page);
    await expectAccessible(page);
    await page.goto("/session");
    await expect(page.getByRole("button", { name: "Submit answer" })).toBeVisible();
    await expectAccessible(page);
  });
});

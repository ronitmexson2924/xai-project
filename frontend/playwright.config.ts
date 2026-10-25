import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests against the real stack: a freshly reset Postgres database (pcg_e2e), the FastAPI
 * backend, and the production build of the frontend. Run `npm run build` first.
 *   PYTHON=../backend/.venv/bin/python npx playwright test
 */
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://localhost:3005",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // a preinstalled browser (e.g. in a sandbox) instead of `npx playwright install`
        launchOptions: process.env.PW_CHROMIUM_PATH
          ? { executablePath: process.env.PW_CHROMIUM_PATH }
          : {},
      },
    },
  ],
  webServer: [
    {
      command: `cd ../backend && ${python} ../frontend/e2e/setup_backend.py`,
      url: "http://localhost:8000/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run start -- -p 3005",
      url: "http://localhost:3005",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: "http://localhost:3005",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "cd ../backend && .venv/bin/uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/health",
      reuseExistingServer: false,
      timeout: 20000,
    },
    {
      command: "npm run start -- -p 3005",
      url: "http://localhost:3005",
      reuseExistingServer: false,
      timeout: 20000,
    },
  ],
});

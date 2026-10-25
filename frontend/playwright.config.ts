import { defineConfig, devices } from "@playwright/test";

// End-to-end against the real backend and a real Postgres database. Before running:
//   createdb pcg_e2e && cd backend && DATABASE_URL=... alembic upgrade head
//   DATABASE_URL=... python -m app.graph.seed ../content
//   cd frontend && npm run build && E2E_DATABASE_URL=... npx playwright test
// PYTHON points at the backend's interpreter (default: python). PW_CHROMIUM may point at a
// preinstalled Chromium when the bundled one is not downloaded.
const database = process.env.E2E_DATABASE_URL || "postgresql+psycopg://pcg:pcg@localhost:5432/pcg_e2e";
const python = process.env.PYTHON || "python";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://localhost:3005",
    trace: "retain-on-failure",
    launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `cd ../backend && ${python} -m uvicorn app.main:app --port 8000`,
      url: "http://localhost:8000/health",
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        DATABASE_URL: database,
        JWT_SECRET: "e2e-only-secret-".padEnd(48, "x"),
        CORS_ORIGINS: "http://localhost:3005",
        INCLUDE_DRAFT_ITEMS: "true", // items are still awaiting review
        EXPORT_SALT: "e2e-export-salt-value",
        RATE_LIMIT_REQUESTS_PER_MINUTE: "600",
        AUTH_RATE_LIMIT_PER_MINUTE: "10",
        AUTH_IP_RATE_LIMIT_PER_MINUTE: "100",
      },
    },
    {
      command: "npm run start -- -p 3005",
      url: "http://localhost:3005",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});

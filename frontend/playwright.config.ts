import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const snapChromiumBinary = "/snap/chromium/current/usr/lib/chromium-browser/chrome";
const localChromiumPath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ??
  (existsSync(snapChromiumBinary) ? snapChromiumBinary : undefined);

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    launchOptions: localChromiumPath
      ? {
          executablePath: localChromiumPath,
          args: ["--no-sandbox"],
        }
      : undefined,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node ./tests/e2e/mock-backend.mjs",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 30_000,
    },
    {
      command: "API_URL=http://127.0.0.1:8000 node ./node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});

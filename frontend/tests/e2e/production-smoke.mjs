import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { chromium } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "https://www.codebaseatlas.com";
const SUMMARY_PATH = process.env.SMOKE_SUMMARY_PATH || "";
const SCREENSHOT_PATH = process.env.SMOKE_SCREENSHOT_PATH || "";

function ensureParentDir(path) {
  if (!path) {
    return;
  }
  mkdirSync(dirname(path), { recursive: true });
}

function writeArtifact(path, value) {
  if (!path) {
    return;
  }
  ensureParentDir(path);
  writeFileSync(path, JSON.stringify(value, null, 2));
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const consoleErrors = [];
  const summary = {
    baseUrl: BASE_URL,
    startedAt: new Date().toISOString(),
    ok: false,
    checks: {},
    consoleErrors,
  };

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      // Browser-level resource loading failures (e.g. from admin-gated 404 fetches) are
      // tracked via homeChecks status codes — don't double-count them as JS errors.
      if (!text.startsWith("Failed to load resource:")) {
        consoleErrors.push(text);
      }
    }
  });

  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 60000 });

    const homeChecks = await page.evaluate(async () => {
      const [health, ops, history] = await Promise.all([
        fetch("/health"),
        fetch("/api/ops/summary"),
        fetch("/api/history/runs?limit=6"),
      ]);
      const healthPayload = await health.json();
      return {
        health: health.status,
        ops: ops.status,
        history: history.status,
        service: healthPayload.service,
        publicHealthStatus: healthPayload.status,
      };
    });
    summary.checks.home = homeChecks;

    if (homeChecks.health !== 200) {
      throw new Error(`Homepage API checks failed: ${JSON.stringify(homeChecks)}`);
    }
    if (!["codebase-atlas-backend"].includes(homeChecks.service)) {
      throw new Error(`Unexpected health service payload: ${JSON.stringify(homeChecks)}`);
    }
    if (![200, 401, 404].includes(homeChecks.ops) || ![200, 401, 404].includes(homeChecks.history)) {
      throw new Error(`Protected API checks returned unexpected statuses: ${JSON.stringify(homeChecks)}`);
    }

    await page.goto(`${BASE_URL}/scout`, { waitUntil: "networkidle", timeout: 60000 });
    await page.getByRole("button", { name: "GitLab" }).click();
    await page.getByPlaceholder("e.g. nextjs auth starter or rag pipeline langchain").fill("fastapi");
    await page.getByRole("button", { name: "Run Scout" }).click();
    await page.waitForSelector("text=Ranked Results", { timeout: 90000 });
    summary.checks.scout = { ok: true };

    await page.goto(`${BASE_URL}/map`, { waitUntil: "networkidle", timeout: 60000 });
    await page.getByPlaceholder("tiangolo/fastapi or https://github.com/owner/repo").fill("tiangolo/fastapi");
    await page.getByRole("button", { name: "Run Map" }).click();
    await page.waitForSelector("text=Map result", { timeout: 90000 });
    summary.checks.map = { ok: true };

    await page.goto(`${BASE_URL}/review?repo=tiangolo/fastapi`, { waitUntil: "networkidle", timeout: 60000 });
    const reviewVisible = await page.getByRole("button", { name: /Run Review/i }).isVisible();
    summary.checks.review = { reviewVisible };
    if (!reviewVisible) {
      throw new Error("Review page did not render the Run Review action.");
    }

    const postFlowHealth = await page.evaluate(async () => {
      const health = await fetch("/health");
      return await health.json();
    });
    summary.checks.postFlowHealth = postFlowHealth;
    if (postFlowHealth.status !== "ok") {
      throw new Error(`Public health is degraded after live flows: ${JSON.stringify(postFlowHealth)}`);
    }

    if (consoleErrors.length > 0) {
      throw new Error(`Console errors detected: ${consoleErrors.join(" | ")}`);
    }
    summary.ok = true;
  } catch (error) {
    summary.error = error instanceof Error ? error.message : String(error);
    if (SCREENSHOT_PATH) {
      ensureParentDir(SCREENSHOT_PATH);
      await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
      summary.screenshotPath = SCREENSHOT_PATH;
    }
    throw error;
  } finally {
    summary.finishedAt = new Date().toISOString();
    writeArtifact(SUMMARY_PATH, summary);
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});

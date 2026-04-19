import { chromium } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "https://www.codebaseatlas.com";

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const consoleErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
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
      const opsPayload = await ops.json();
      return {
        health: health.status,
        ops: ops.status,
        history: history.status,
        github: healthPayload.github?.status,
        opsStatus: opsPayload.status,
        attentionMessage: opsPayload.attention_message,
      };
    });

    if (homeChecks.health !== 200 || homeChecks.ops !== 200 || homeChecks.history !== 200) {
      throw new Error(`Homepage API checks failed: ${JSON.stringify(homeChecks)}`);
    }
    await page.goto(`${BASE_URL}/scout`, { waitUntil: "networkidle", timeout: 60000 });
    await page.getByPlaceholder("e.g. nextjs auth starter or rag pipeline langchain").fill("fastapi");
    await page.getByRole("button", { name: "Run Scout" }).click();
    await page.waitForSelector("text=Ranked Results", { timeout: 60000 });

    await page.goto(`${BASE_URL}/map`, { waitUntil: "networkidle", timeout: 60000 });
    await page.getByPlaceholder("tiangolo/fastapi or https://github.com/owner/repo").fill("tiangolo/fastapi");
    await page.getByRole("button", { name: "Run Map" }).click();
    await page.waitForSelector("text=Map result", { timeout: 90000 });

    await page.goto(`${BASE_URL}/review?repo=tiangolo/fastapi`, { waitUntil: "networkidle", timeout: 60000 });
    await page.getByRole("button", { name: /Run Review/i }).isVisible();

    const postFlowHealth = await page.evaluate(async () => {
      const health = await fetch("/health");
      return await health.json();
    });
    if (!["ok", "configured"].includes(postFlowHealth.github?.status)) {
      throw new Error(`GitHub auth health is degraded after live flows: ${JSON.stringify(postFlowHealth)}`);
    }

    if (consoleErrors.length > 0) {
      throw new Error(`Console errors detected: ${consoleErrors.join(" | ")}`);
    }
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});

import { expect, test } from "@playwright/test";

test("results page generates a devcontainer using the analysis job id", async ({ page }) => {
  const devcontainerRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/devcontainer/")) {
      devcontainerRequests.push(request.url());
    }
  });

  await page.goto("/results/456");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: "Generate DevContainer" }).click();

  await expect.poll(() => devcontainerRequests.at(-1) ?? "").toContain("/api/devcontainer/123/generate");
  await expect(page.getByLabel("Generated devcontainer.json")).toContainText('"name": "atlas-dev-python"');
  await expect(page.getByRole("link", { name: /Download devcontainer v1 as ZIP/i })).toBeVisible();
});

test("review page submits a repo, polls the backend, and expands findings", async ({ page }) => {
  const reviewRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/review")) {
      reviewRequests.push(request.url());
    }
  });

  await page.goto("/review");
  await page.getByPlaceholder("https://github.com/owner/repo").fill("https://github.com/MentalVibez/ai-agent-orchestrator");
  await page.getByRole("button", { name: "Run Review" }).click();

  await expect.poll(() => reviewRequests.some((url) => url.endsWith("/api/review/"))).toBeTruthy();

  await page.goto("/review?result_id=review-result-789");
  const findingButton = page.getByRole("button", {
    name: /Healthchecks are present but tracing is still missing/i,
  });
  await expect(findingButton).toBeVisible();
  await findingButton.click();
  await expect(page.getByText("Add Sentry or OpenTelemetry tracing for the critical request path.")).toBeVisible();
});

test("map page fetches endpoint groups and toggles the accordion", async ({ page }) => {
  await page.goto("/map");
  await page
    .getByPlaceholder("tiangolo/fastapi or https://github.com/owner/repo")
    .fill("MentalVibez/ai-agent-orchestrator");
  await page.getByRole("button", { name: "Run Map" }).click();

  await expect(page.getByRole("heading", { name: "MentalVibez/ai-agent-orchestrator" })).toBeVisible();
  await expect(page.getByText("The API surface is centered on operational status and analysis workflows.")).toBeVisible();
  await expect(page.getByText("/health")).toBeVisible();

  await page.getByRole("button", { name: /Health & Status/i }).click();
  await expect(page.getByText("/health")).toHaveCount(0);
  await page.getByRole("button", { name: /Health & Status/i }).click();
  await expect(page.getByText("/ready")).toBeVisible();
});

test("scout page searches, toggles providers, reveals evidence, and sends the result to Atlas", async ({ page }) => {
  await page.goto("/scout");

  await page.getByRole("button", { name: "GitLab" }).click();
  await expect(page.getByRole("button", { name: "GitLab" })).toContainText("GitLab");

  await page.getByPlaceholder("owner/repo, GitHub URL, or e.g. rag pipeline langchain").fill("MentalVibez/ai-agent-orchestrator");
  await page.getByRole("button", { name: "Run Scout" }).click();

  await expect(page.getByText("One strong repository matched the query with high quality and relevance.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Show evidence" })).toBeVisible();

  await page.getByRole("button", { name: "Show evidence" }).click();
  await expect(page.getByText("README", { exact: true })).toBeVisible();
  await expect(page.getByText("MIT")).toBeVisible();

  await page.getByRole("button", { name: "Send to Atlas" }).click();
  await page.waitForURL(/\/analyze\?job_id=123&tab=setup$/, { timeout: 20_000 });
});

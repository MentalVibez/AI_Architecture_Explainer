import { expect, test } from "@playwright/test";

test("submits a repo URL and renders the mocked results report", async ({ page }) => {
  test.slow();
  const browserErrors: string[] = [];
  const apiRequests: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/analyze")) {
      apiRequests.push(request.url());
    }
  });

  await page.goto("/");
  await page.waitForLoadState("networkidle");

  const repoInput = page.getByPlaceholder("Paste a public GitHub repository URL");
  const submitButton = page.getByRole("button", { name: "Open Atlas" });

  await repoInput.click();
  await repoInput.pressSequentially("https://github.com/MentalVibez/ai-agent-orchestrator/");
  await expect(repoInput).toHaveValue("https://github.com/MentalVibez/ai-agent-orchestrator/");
  expect(browserErrors).toEqual([]);
  await expect(submitButton).toBeEnabled();
  await submitButton.click();
  await expect.poll(() => apiRequests.length).toBeGreaterThan(0);

  await page.waitForURL(/\/analyze\?job_id=123&tab=setup$/, { timeout: 20_000 });
  await page.waitForURL(/\/results\/456\?tab=setup$/, { timeout: 60_000 });

  await expect(
    page.getByRole("heading", { name: "MentalVibez/ai-agent-orchestrator" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Architecture Diagram" })).toBeVisible();
  await expect(page.getByText("Codebase Guide")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Understand the system before you change it." }),
  ).toBeVisible();
  await expect(page.getByText("frontend/app/page.tsx").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Technical", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Non-Technical", exact: true })).toBeVisible();
  await expect(
    page.getByText("Mocked backend response used for Playwright smoke coverage."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Setup, debug, and change-readiness signals" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Setup" })).toHaveClass(/border-\[#4d7cff\]/);
  await expect(page.getByText(".env.example present")).toBeVisible();
  await page.getByRole("button", { name: "Debug" }).click();
  await expect(page.getByText("Error tracking (Sentry / OpenTelemetry)")).toBeVisible();
  await page.getByRole("button", { name: "Change" }).click();
  await expect(page.getByText("Blast radius hotspots")).toBeVisible();
});

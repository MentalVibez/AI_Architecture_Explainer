import { expect, test } from "@playwright/test";

test("submits a repo URL and renders the mocked results report", async ({ page }) => {
  test.slow();

  await page.goto("/");

  await page
    .getByPlaceholder("https://github.com/owner/repo")
    .fill("https://github.com/MentalVibez/ai-agent-orchestrator/");

  await page.getByRole("button", { name: "Analyze →" }).click();

  await page.waitForURL(/\/analyze\?job_id=123$/, { timeout: 20_000 });
  await page.waitForURL(/\/results\/456$/, { timeout: 60_000 });

  await expect(
    page.getByRole("heading", { name: "MentalVibez/ai-agent-orchestrator" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Architecture Diagram" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Technical", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Non-Technical", exact: true })).toBeVisible();
  await expect(
    page.getByText("Mocked backend response used for Playwright smoke coverage."),
  ).toBeVisible();
});

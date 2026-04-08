import { expect, test } from "@playwright/test";

test("keeps GitHub in the footer only as the Open source link", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: "Star on GitHub" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "GitHub Repository" })).toHaveCount(0);

  const openSourceLink = page.getByRole("link", { name: /Open source/i });

  await expect(openSourceLink).toBeVisible();
  await expect(openSourceLink).toHaveAttribute(
    "href",
    "https://github.com/MentalVibez/AI_Architecture_Explainer",
  );
}
);

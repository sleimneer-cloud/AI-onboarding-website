import { expect, test } from "@playwright/test";

test("renders the scaffold and exposes process health", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "IX Value Loop" })).toBeVisible();

  const healthResponse = await request.get("http://127.0.0.1:8000/health");
  expect(healthResponse.status()).toBe(200);
  await expect(healthResponse.json()).resolves.toEqual({
    status: "ok",
    service: "ix-value-loop",
    version: "0.1.0",
  });
});

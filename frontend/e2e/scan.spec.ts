import { test, expect } from "@playwright/test";

test.describe("扫描页面", () => {
  test("扫描页正确加载（无需摄像头）", async ({ page }) => {
    await page.goto("/scan");
    await expect(page.getByRole("heading", { name: "人脸识别门禁" })).toBeVisible();
    await expect(page.locator('button:has-text("开始识别")')).toBeVisible();
  });

  test("识别结果区域初始状态", async ({ page }) => {
    await page.goto("/scan");
    await expect(page.locator("text=等待识别...")).toBeVisible();
  });
});

test.describe("考勤记录页", () => {
  test("未登录访问考勤记录页跳转到登录", async ({ page }) => {
    await page.goto("/records");
    await expect(page).toHaveURL(/\/login/);
  });
});

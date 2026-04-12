import { test, expect } from "@playwright/test";

test.describe("导航和页面加载", () => {
  test("首页正确加载", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/人脸识别门禁系统/);
    await expect(page.locator("text=人脸识别门禁系统")).toBeVisible();
  });

  test("404 页面", async ({ page }) => {
    await page.goto("/nonexistent-page");
    await expect(page.locator("text=抱歉，您访问的页面不存在")).toBeVisible();
  });

  test("登录页正确加载", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("text=管理员登录")).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("注册页正确加载", async ({ page }) => {
    await page.goto("/register");
    await expect(page.locator("text=用户注册").first()).toBeVisible();
    await expect(page.locator('input[placeholder*="工号"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="姓名"]')).toBeVisible();
  });

  test("未登录时访问需认证页面跳转到登录", async ({ page }) => {
    await page.goto("/records");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("登录流程", () => {
  test("空密码提交显示错误", async ({ page }) => {
    await page.goto("/login");
    await page.click('button:has-text("登录")');
    await expect(page.locator(".el-form-item__error")).toBeVisible();
  });
});

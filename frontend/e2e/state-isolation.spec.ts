import { expect, test } from "@playwright/test";

import { gotoApp, openNav, selectFromPicker, TINY_PNG } from "./helpers";

test("切换拼接功能不串状态，返回后恢复本功能选择", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "工具", "tools", "图片拼接");
  await expect(page.getByRole("heading", { name: "图片拼接", exact: true })).toBeVisible();

  await selectFromPicker(page, "E2E 隐藏输入");
  await expect(page.getByRole("button", { name: "移除", exact: true })).toHaveCount(1);
  await expect(page.getByText("E2E 隐藏输入").first()).toBeVisible();
  const drop = page.getByRole("button", { name: /点击或拖拽上传/ });
  await expect(drop.getByText("E2E 隐藏输入")).toBeVisible();

  await openNav(page, "工具", "tools", "视频拼接");
  await expect(page.getByRole("heading", { name: "视频拼接", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "移除", exact: true })).toHaveCount(0);
  await expect(page.getByText("E2E 隐藏输入")).toHaveCount(0);

  await openNav(page, "工具", "tools", "图片拼接");
  await expect(page.getByRole("button", { name: "移除", exact: true })).toHaveCount(1);
  await expect(page.getByText("E2E 隐藏输入").first()).toBeVisible();

  await page.getByRole("button", { name: "移除", exact: true }).click();
  await expect(page.getByRole("button", { name: "移除", exact: true })).toHaveCount(0);
  await expect(page.getByText("E2E 隐藏输入")).toHaveCount(0);
});

test("拖入错误文件类型会被拒绝并提示", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "工具", "tools", "视频拼接");
  await expect(page.getByRole("heading", { name: "视频拼接", exact: true })).toBeVisible();

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "bad.png",
    mimeType: "image/png",
    buffer: TINY_PNG,
  });
  await expect(page.getByText(/不支持的文件类型/)).toBeVisible();
  await expect(page.getByText(/bad\.png/)).toBeVisible();
  await expect(page.getByRole("button", { name: "移除", exact: true })).toHaveCount(0);
});

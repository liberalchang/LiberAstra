import { expect, test } from "@playwright/test";

import { gotoApp, openNav, TINY_PNG } from "./helpers";

test("图像编辑与图片增强切换不串文件状态", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "图像", "image", "图生图与编辑");
  await expect(page.getByRole("heading", { name: "图生图与编辑", exact: true })).toBeVisible();

  const input = page.locator('input[type="file"]').first();
  await input.waitFor({ state: "attached" });
  await input.setInputFiles({ name: "e2e-edit.png", mimeType: "image/png", buffer: TINY_PNG });
  await expect(page.getByText("e2e-edit.png").first()).toBeVisible();

  await openNav(page, "工具", "tools", "图片增强");
  await expect(page.getByRole("heading", { name: "图片增强", exact: true })).toBeVisible();
  await expect(page.getByText("e2e-edit.png")).toHaveCount(0);

  await openNav(page, "图像", "image", "图生图与编辑");
  await expect(page.getByText("e2e-edit.png")).toHaveCount(0);
});

test("视频包 avatar 与 i2v 切换不串图片状态", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "视频", "video", "数字人口播");
  const input = page.locator('input[type="file"]').first();
  await input.waitFor({ state: "attached" });
  await input.setInputFiles({ name: "e2e-avatar.png", mimeType: "image/png", buffer: TINY_PNG });
  await expect(page.getByText("e2e-avatar.png").first()).toBeVisible();

  await openNav(page, "视频", "video", "图生视频");
  await expect(page.getByText("e2e-avatar.png")).toHaveCount(0);
});

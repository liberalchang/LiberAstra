import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

test("历史作品只显示本功能产出，并可查看全部", async ({ page }) => {
  await gotoApp(page);

  await openNav(page, "图像", "image", "文生图");
  await expect(page.getByRole("heading", { name: "文生图", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 生成图").first()).toBeVisible();
  await expect(page.getByText("E2E 图生图")).toHaveCount(0);
  await expect(page.getByText("E2E 图片增强")).toHaveCount(0);

  await page.getByRole("link", { name: "查看全部", exact: true }).click();
  await expect(page).toHaveURL(/\/assets\?tab=image/);
  await expect(page.getByRole("heading", { name: "资产库", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 生成图").first()).toBeVisible();
  await expect(page.getByText("E2E 图生图").first()).toBeVisible();
  await expect(page.getByText("E2E 图片增强").first()).toBeVisible();

  await openNav(page, "图像", "image", "图生图与编辑");
  await expect(page.getByRole("heading", { name: "图生图与编辑", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 图生图").first()).toBeVisible();
  await expect(page.getByText("E2E 图片增强")).toHaveCount(0);
  await expect(page.getByText("E2E 生成图")).toHaveCount(0);

  await openNav(page, "工具", "tools", "图片增强");
  await expect(page.getByRole("heading", { name: "图片增强", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 图片增强").first()).toBeVisible();
  await expect(page.getByText("E2E 图生图")).toHaveCount(0);

  await openNav(page, "语音", "speech", "语音转文字");
  await expect(page.getByRole("heading", { name: "语音转文字", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 字幕").first()).toBeVisible();
  await expect(page.getByText("E2E 分镜文本")).toHaveCount(0);

  await openNav(page, "语音", "speech", "文字转语音");
  await expect(page.getByRole("heading", { name: "文字转语音", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 语音").first()).toBeVisible();
  await expect(page.getByText("E2E 换音")).toHaveCount(0);

  await openNav(page, "语音", "speech", "音色替换");
  await expect(page.getByRole("heading", { name: "换音", exact: true })).toBeVisible();
  await expect(page.getByText("E2E 换音").first()).toBeVisible();
  await expect(page.getByText("E2E 语音")).toHaveCount(0);
});

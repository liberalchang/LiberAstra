import { expect, test } from "@playwright/test";

import { gotoApp, openNav, TINY_PNG } from "./helpers";

test("素材库工具栏：显示隐藏资源在左，上传资源在右", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "资源", "resources", "素材库");

  const upload = page.getByRole("button", { name: "上传资源", exact: true });
  const hidden = page.getByLabel("显示隐藏资源");
  await expect(upload).toBeVisible();
  await expect(hidden).toBeVisible();

  const hiddenBox = await hidden.boundingBox();
  const uploadBox = await upload.boundingBox();
  expect(hiddenBox!.x + hiddenBox!.width).toBeLessThan(uploadBox!.x);

  const group = upload.locator("xpath=..");
  const toolbar = group.locator("xpath=..");
  const groupBox = await group.boundingBox();
  const toolbarBox = await toolbar.boundingBox();
  expect(groupBox!.x + groupBox!.width).toBeGreaterThan(toolbarBox!.x + toolbarBox!.width - 4);

  await page.getByRole("button", { name: "工作", exact: true }).click();
  await expect(upload).toBeVisible();
  await expect(hidden).toHaveCount(0);
  const workGroup = upload.locator("xpath=..");
  const workGroupBox = await workGroup.boundingBox();
  const workToolbarBox = await workGroup.locator("xpath=..").boundingBox();
  expect(workGroupBox!.x + workGroupBox!.width).toBeGreaterThan(
    workToolbarBox!.x + workToolbarBox!.width - 4,
  );
});

test("拼接上传默认隐藏，选择器可见，素材库可转正", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "工具", "tools", "图片拼接");
  await expect(page.getByRole("heading", { name: "图片拼接", exact: true })).toBeVisible();

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "e2e-upload.png",
    mimeType: "image/png",
    buffer: TINY_PNG,
  });
  await expect(page.getByText("e2e-upload.png").first()).toBeVisible();

  await page.getByRole("button", { name: "从资源库选择" }).click();
  const modal = page.locator("div.fixed.inset-0.z-50");
  await expect(modal.getByRole("button").filter({ hasText: "e2e-upload.png" })).toBeVisible();
  await modal.getByRole("button", { name: "关闭", exact: true }).click();

  await openNav(page, "资源", "resources", "素材库");
  await expect(page.getByRole("heading", { name: "资产库", exact: true })).toBeVisible();

  await expect(page.getByText("e2e-upload.png")).toHaveCount(0);
  await expect(page.getByText("E2E 隐藏输入")).toHaveCount(0);

  await page.getByLabel("显示隐藏资源").check();
  await expect(page.getByText("e2e-upload.png").first()).toBeVisible();
  await expect(page.getByText("E2E 隐藏输入").first()).toBeVisible();

  await page.getByRole("button", { name: "移入资源库 e2e-upload.png" }).click();
  await expect(page.getByText("已移入资源库")).toBeVisible();
  await expect(page.getByRole("button", { name: "移入资源库 e2e-upload.png" })).toHaveCount(0);

  await page.getByLabel("显示隐藏资源").uncheck();
  await expect(page.getByText("e2e-upload.png").first()).toBeVisible();
});

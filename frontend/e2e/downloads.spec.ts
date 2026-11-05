import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

test("单资源与工作文件夹下载使用浏览器直链", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "资源", "resources", "素材库");
  await expect(page.getByRole("heading", { name: "资产库", exact: true })).toBeVisible();

  const [single] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载", exact: true }).first().click(),
  ]);
  expect(single.url()).toContain("/api/v1/assets/");
  expect(single.url()).toContain("/download?token=");

  await page.getByRole("button", { name: "工作", exact: true }).click();
  await expect(page.getByRole("button", { name: "选择", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "选择", exact: true }).click();
  await page.locator('input[type="checkbox"]').first().check();

  const [zip] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载", exact: true }).click(),
  ]);
  expect(zip.url()).toContain("/api/v1/assets/jobs/download?token=");
  expect(zip.suggestedFilename()).toMatch(/\.zip$/);
});

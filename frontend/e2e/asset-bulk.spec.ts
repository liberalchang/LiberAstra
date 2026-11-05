import { readFile, stat } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

const SEARCH = "搜索名称、提示词或时间";

async function openAssets(page: Parameters<typeof gotoApp>[0]): Promise<void> {
  await gotoApp(page);
  await openNav(page, "资源", "resources", "素材库");
  await expect(page.getByRole("heading", { name: "资产库", exact: true })).toBeVisible();
}

async function expectZipDownload(page: Parameters<typeof gotoApp>[0]): Promise<void> {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载", exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^liberastra-assets-\d{8}-\d{6}\.zip$/);
  expect(download.url()).toContain("/api/v1/assets/selection/download?token=");
  const filePath = await download.path();
  expect(filePath).toBeTruthy();
  const info = await stat(filePath!);
  expect(info.size).toBeGreaterThan(4);
  const head = await readFile(filePath!);
  expect(head.subarray(0, 4).toString("latin1")).toBe("PK\x03\x04");
}

test("全部页签多选后 ZIP 下载，切换页签清空选择", async ({ page }) => {
  await openAssets(page);
  await page.getByLabel(SEARCH).fill("E2E 批量下载");

  await page.getByRole("button", { name: "选择", exact: true }).click();
  await expect(page.getByText("已选 0 项")).toBeVisible();
  await page.getByLabel("选择 E2E 批量下载A").check();
  await page.getByLabel("选择 E2E 批量下载B").check();
  await expect(page.getByText("已选 2 项")).toBeVisible();

  await expectZipDownload(page);

  await page.getByRole("main").getByRole("button", { name: "图片", exact: true }).click();
  await expect(page.getByRole("button", { name: "选择", exact: true })).toBeVisible();
  await expect(page.getByText(/已选 \d+ 项/)).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: /^选择 / })).toHaveCount(0);
});

test("视频页签支持多选下载", async ({ page }) => {
  await openAssets(page);
  await page.getByRole("main").getByRole("button", { name: "视频", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 批量视频下载");

  await page.getByRole("button", { name: "选择", exact: true }).click();
  await page.getByLabel("选择 E2E 批量视频下载").check();
  await expect(page.getByText("已选 1 项")).toBeVisible();
  await expectZipDownload(page);
});

test("图片页签批量删除只删资产并显示确认弹窗", async ({ page }) => {
  await openAssets(page);
  await page.getByRole("main").getByRole("button", { name: "图片", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 批量删除");

  await page.getByRole("button", { name: "选择", exact: true }).click();
  await page.getByLabel("选择 E2E 批量删除").check();
  await page.getByRole("button", { name: "删除", exact: true }).click();

  const dialog = page.getByRole("dialog", { name: "删除选中的资产？" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("将删除 1 个资产");
  await expect(dialog).not.toContainText("可能被画布引用");
  await dialog.getByRole("button", { name: "删除", exact: true }).click();

  await expect(page.getByText("已删除 1 个资产")).toBeVisible();
  await expect(page.getByText("E2E 批量删除", { exact: true })).toHaveCount(0);
});

test("隐藏页签：红色标签、无显示隐藏资源选框、批量导入资源库", async ({ page }) => {
  await openAssets(page);
  const hiddenTab = page.getByRole("button", { name: "隐藏", exact: true });
  await expect(hiddenTab).toHaveClass(/text-danger/);
  await hiddenTab.click();
  await expect(hiddenTab).toHaveClass(/bg-danger/);
  await expect(page.getByLabel("显示隐藏资源")).toHaveCount(0);

  await page.getByLabel(SEARCH).fill("E2E 隐藏批量导入");
  await expect(page.getByText("E2E 隐藏批量导入", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "选择", exact: true }).click();
  await page.getByLabel("选择 E2E 隐藏批量导入").check();
  await expectZipDownload(page);

  await page.getByRole("button", { name: "批量导入资源库", exact: true }).click();
  await expect(page.getByText("已导入 1 个资源")).toBeVisible();
  await expect(page.getByLabel("选择 E2E 隐藏批量导入")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "选择", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "全部", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 隐藏批量导入");
  await expect(page.getByText("E2E 隐藏批量导入", { exact: true })).toBeVisible();
});

test("隐藏页签批量删除提示画布引用风险", async ({ page }) => {
  await openAssets(page);
  await page.getByRole("button", { name: "隐藏", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 隐藏批量删除");

  await page.getByRole("button", { name: "选择", exact: true }).click();
  await page.getByLabel("选择 E2E 隐藏批量删除").check();
  await page.getByRole("button", { name: "删除", exact: true }).click();

  const dialog = page.getByRole("dialog", { name: "删除选中的资产？" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("将删除 1 个资产");
  await expect(dialog).toContainText("可能被画布引用");
  await dialog.getByRole("button", { name: "删除", exact: true }).click();

  await expect(page.getByText("已删除 1 个资产")).toBeVisible();
  await expect(page.getByText("E2E 隐藏批量删除", { exact: true })).toHaveCount(0);
});

test("角色库图片不出现在资产库与隐藏页签", async ({ page }) => {
  await openAssets(page);
  await page.getByLabel(SEARCH).fill("E2E 角色图");
  await expect(page.getByText(/E2E 角色图/)).toHaveCount(0);

  await page.getByLabel("显示隐藏资源").check();
  await expect(page.getByText(/E2E 角色图/)).toHaveCount(0);

  await page.getByRole("button", { name: "隐藏", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 角色图");
  await expect(page.getByText(/E2E 角色图/)).toHaveCount(0);

  await page.getByRole("button", { name: "全部", exact: true }).click();
  await page.getByLabel(SEARCH).fill("E2E 生成图");
  await expect(page.getByText("E2E 生成图", { exact: true })).toBeVisible();
});

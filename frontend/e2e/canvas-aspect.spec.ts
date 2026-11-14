import { expect, test } from "@playwright/test";

test("canvas t2i aspect selection applies both sides", async ({ page }) => {
  await page.goto("/canvas?mode=list");
  await expect(page.getByRole("button", { name: "新建画布" })).toBeVisible();
  await page.getByRole("button", { name: "新建画布" }).click();
  await expect(page.getByRole("button", { name: "全部功能" })).toBeVisible();
  await page.getByRole("button", { name: "全部功能" }).click();
  await page.getByRole("button", { name: "文生图", exact: true }).click();

  const inspector = page.locator("aside").filter({ hasText: "宽高比" }).last();
  const aspect = inspector.getByRole("button", { name: /宽高比/ });
  await expect(aspect).toBeVisible({ timeout: 20_000 });

  await aspect.click();
  const sizes = (await page.getByRole("option").allInnerTexts())
    .map((text) => text.match(/\d+×\d+/)?.[0])
    .filter((size): size is string => Boolean(size));
  expect(new Set(sizes).size).toBe(sizes.length);
  await page.getByRole("option", { name: /3:4/ }).click();
  await expect(aspect).toContainText("3:4");
  await expect(aspect).toContainText("768×1024");

  await aspect.click();
  await page.getByRole("option", { name: "自定义" }).click();
  const width = inspector.getByLabel("自定义宽度");
  const height = inspector.getByLabel("自定义高度");
  await width.fill("832");
  await width.press("Enter");
  await height.fill("640");
  await height.press("Enter");
  await expect(aspect).toContainText("自定义");
  await expect(aspect).toContainText("832×640");
});

test("image page custom aspect can be used", async ({ page }) => {
  await page.goto("/image/generate");
  const aspect = page.getByRole("button", { name: /宽高比/ });
  await expect(aspect).toBeVisible();
  await aspect.click();
  await page.getByRole("option", { name: "自定义" }).click();
  await page.getByLabel("自定义宽度").fill("832");
  await page.getByLabel("自定义宽度").press("Enter");
  await page.getByLabel("自定义高度").fill("640");
  await page.getByLabel("自定义高度").press("Enter");
  await expect(aspect).toContainText("自定义");
  await expect(aspect).toContainText("832×640");
});

test("canvas menu custom function can be created and used", async ({ page }) => {
  await page.goto("/canvas?mode=list");
  await page.getByRole("button", { name: "菜单设置" }).click();

  const imageSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "图像", exact: true }),
  });
  await expect(imageSection.getByRole("heading", { name: "文生图", exact: true })).toBeVisible();
  await imageSection.getByRole("button", { name: "添加功能" }).click();
  await imageSection.getByLabel("简称").fill("测试生图");
  await page.getByRole("button", { name: "完成编辑" }).click();
  await expect(page.getByRole("button", { name: "完成编辑" })).toHaveCount(0);

  await page.goto("/canvas?mode=list");
  await page.getByRole("button", { name: "新建画布" }).click();
  await expect(page.getByRole("button", { name: "全部功能" })).toBeVisible();
  await page.getByRole("button", { name: "全部功能" }).click();
  await expect(page.getByRole("button", { name: "文生图", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "测试生图", exact: true }).click();

  const inspector = page.locator("aside").filter({ hasText: "宽高比" }).last();
  await expect(inspector.getByRole("button", { name: /宽高比/ })).toBeVisible({ timeout: 20_000 });
});

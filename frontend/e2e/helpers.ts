import { expect, type Page } from "@playwright/test";

/** 通过侧栏分组浮层做客户端跳转，保留 SPA 状态。 */
export async function openNav(
  page: Page,
  group: string,
  panelId: string,
  link: string,
): Promise<void> {
  const nav = page.locator("aside").first();
  await nav.getByRole("button", { name: group, exact: true }).click();
  const panel = page.locator(`#nav-panel-${panelId}`);
  await expect(panel).toBeVisible();
  await panel.getByRole("link", { name: link, exact: true }).click();
  await expect(panel).toHaveCount(0);
}

export async function gotoApp(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.locator("aside").first()).toBeVisible();
}

/** 仅用于上传测试的小 PNG 字节；内容有效性不影响文件名/可见性断言。 */
export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

export async function selectFromPicker(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: "从资源库选择" }).click();
  const modal = page.locator("div.fixed.inset-0.z-50");
  await expect(modal).toBeVisible();
  await modal.getByRole("button").filter({ hasText: label }).first().click();
  await page.getByRole("button", { name: "确认选择" }).click();
}

import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

test("系统设置可保存语音转文字超时", async ({ page }) => {
  await gotoApp(page);
  await openNav(page, "设置", "settings", "系统设置");

  const input = page.getByLabel("语音转文字超时");
  await expect(input).toHaveValue("1800");
  await input.fill("2400");
  await input.blur();

  const form = page.locator("form", { has: input });
  await form.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("已保存，下一个任务起生效。")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("语音转文字超时")).toHaveValue("2400");
});

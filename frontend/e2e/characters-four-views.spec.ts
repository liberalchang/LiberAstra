import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const viewImage = path.join(here, "fixtures", "character-view.png");
const badRatioImage = path.join(here, "fixtures", "character-view-bad-ratio.png");

test("four-slot upload composes six images and downloads the card", async ({ page }) => {
  const name = `E2E 四视图 ${Date.now()}`;
  await page.goto("/resources/characters");
  await page.getByRole("tab", { name: "上传新建" }).click();

  const inputs = page.locator('input[type="file"]');
  await expect(page.getByText("9:16 · 短边≥640")).toHaveCount(4);
  await inputs.nth(0).setInputFiles(badRatioImage);
  await expect(page.getByText(/面部特写必须是 9:16（当前 800×1280）/)).toBeVisible();

  for (let index = 0; index < 4; index += 1) {
    await inputs.nth(index).setInputFiles(viewImage);
    if (index === 0) {
      await expect(page.locator('button[class*="aspect-[9/16]"] img')).toHaveCount(1);
    }
  }
  await page.getByPlaceholder("角色名称").fill(name);
  const save = page.getByRole("button", { name: /补全并创建|合成并创建/ });
  await expect(save).toBeEnabled();
  await save.click();

  // 切换页签后仍能看到同一个任务的状态与结果
  await page.getByRole("tab", { name: "修改已有角色" }).click();
  expect(await page.locator("body").innerText()).not.toContain("0000");
  await expect(page.getByText(/六张设定图已更新/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "上传新建" }).click();
  await expect(page.getByText(/六张设定图已更新/)).toBeVisible();

  const heading = page.getByRole("heading", { name, exact: true });
  await expect(heading).toBeVisible({ timeout: 30_000 });
  const card = heading.locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
  await expect(card.locator("img")).toHaveCount(6);
  await expect(card.getByLabel("下载角色卡")).toBeEnabled();

  // 修改已有角色带入图片后，切到上传新建不能残留上一位角色的槽图
  await page.getByRole("tab", { name: "修改已有角色" }).click();
  await page.locator("select").first().selectOption({ label: name });
  await expect(page.locator('button[class*="aspect-[9/16]"] img')).toHaveCount(4);
  await page.getByRole("tab", { name: "上传新建" }).click();
  await expect(page.locator('button[class*="aspect-[9/16]"] img')).toHaveCount(0);

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    card.getByLabel("下载角色卡").click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^character-\d+\.zip$/);

  await card.getByLabel("删除").click();
  await expect(heading).toBeHidden();
});

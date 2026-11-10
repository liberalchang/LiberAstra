import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

const DOCTOR_RESULT = {
  pack: "minimax_h3_i2v",
  provider: { id: 1, name: "Mock ComfyUI", base_url: "http://mock:8188" },
  status: "fail",
  checked_at: "2026-11-10T00:00:00Z",
  summary: { pass: 1, warn: 1, fail: 1, skip: 0 },
  checks: [
    { id: "structure", label: "结构", status: "pass", detail: "ok", items: [] },
    {
      id: "models",
      label: "模型",
      status: "fail",
      detail: "缺 1 个必需模型",
      items: [
        {
          name: "loras/missing.safetensors",
          status: "fail",
          optional: false,
          hint: "放到 ComfyUI/models/loras/",
        },
      ],
    },
    { id: "alignment", label: "对齐", status: "warn", detail: "默认值未对齐", items: [] },
  ],
};

test("工作流包体检显示结果面板", async ({ page }) => {
  await page.route("**/api/v1/providers", async (route) => {
    await route.fulfill({
      json: [
        {
          id: 1,
          name: "Mock ComfyUI",
          type: "comfyui",
          base_url: "http://mock:8188",
          enabled: true,
          capabilities: ["image", "video"],
        },
      ],
    });
  });
  await page.route("**/api/v1/workflows/*/doctor*", async (route) => {
    await route.fulfill({ json: DOCTOR_RESULT });
  });

  await gotoApp(page);
  await openNav(page, "设置", "settings", "工作流包");

  const row = page
    .locator("div.flex.flex-col.gap-2")
    .filter({ hasText: "minimax_h3_i2v" })
    .first();
  await row.getByTitle("体检").click();

  await expect(row.getByText("缺 1 个必需模型")).toBeVisible();
  await expect(row.getByText("loras/missing.safetensors")).toBeVisible();
  await expect(row.getByText("放到 ComfyUI/models/loras/")).toBeVisible();
  await expect(row.getByText("通过 1 · 警告 1 · 失败 1 · 跳过 0")).toBeVisible();
});

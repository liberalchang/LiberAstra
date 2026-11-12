import { expect, test } from "@playwright/test";

import { gotoApp } from "./helpers";

test("动作迁移节点显示两个可选额外参考槽", async ({ page, request }) => {
  await gotoApp(page);
  const token = await page.evaluate(() => {
    const raw = localStorage.getItem("liberastra-auth");
    return raw ? (JSON.parse(raw) as { state?: { token?: string } }).state?.token ?? "" : "";
  });
  expect(token).not.toBe("");

  const created = await request.post("http://127.0.0.1:8010/api/v1/canvases", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: "motion-slots-e2e",
      graph: {
        nodes: [
          {
            id: "function-motion",
            type: "function",
            position: { x: 240, y: 160 },
            data: {
              kind: "function",
              group: "动作迁移",
              pack: "minimax_h3_motion",
              presetId: "preset_motion",
              presetTitle: "动作迁移",
              targetType: "workflow",
              targetId: "minimax_h3_motion",
              targetLabel: "minimax_h3_motion",
              values: {},
              prompt: "",
              run: {
                status: "idle",
                jobId: null,
                assetIds: [],
                error: null,
                published: false,
                reused: false,
              },
            },
          },
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  expect(created.ok()).toBeTruthy();
  const canvas = (await created.json()) as { id: string };

  await page.goto(`/canvas/${canvas.id}`);
  await page.getByTitle("收起到底部").click();
  const node = page.locator(".react-flow__node").filter({ hasText: "动作迁移" }).first();
  await expect(node).toBeVisible();
  await node.click();

  await expect(page.getByText("额外参考 1")).toBeVisible();
  await expect(page.getByText("额外参考 2")).toBeVisible();
  await expect(page.getByLabel("额外参考 1")).toHaveValue("");
  await expect(page.getByLabel("额外参考 2")).toHaveValue("");
});

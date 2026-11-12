import { expect, test } from "@playwright/test";

import { gotoApp } from "./helpers";

test("动作迁移节点显示两个可选额外参考槽", async ({ page, request }) => {
  await gotoApp(page);
  const token = await page.evaluate(() => {
    const raw = localStorage.getItem("liberastra-auth");
    return raw ? (JSON.parse(raw) as { state?: { token?: string } }).state?.token ?? "" : "";
  });
  expect(token).not.toBe("");

  const images = [1, 2, 3].map((index) => ({
    id: `input-image-${index}`,
    varName: `input_image_${index}`,
  }));
  const created = await request.post("http://127.0.0.1:8010/api/v1/canvases", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: "motion-slots-e2e",
      graph: {
        nodes: [
          ...images.map((image, index) => ({
            id: image.id,
            type: "input",
            position: { x: 0, y: 80 + index * 180 },
            data: {
              kind: "input",
              mediaKind: "image",
              assetId: null,
              varName: image.varName,
            },
          })),
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
        edges: images.map((image) => ({
          id: `edge-${image.id}`,
          source: image.id,
          target: "function-motion",
          sourceHandle: `out-${image.id}`,
          targetHandle: "in-function-motion",
        })),
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

  // 目标图片已绑定具体变量后，仍可切回「自动」，让槽位重新按连线顺序分配。
  const target = page.getByLabel("目标图片");
  await expect(target.locator("option")).toHaveCount(4);
  await target.selectOption("input_image_2");
  await expect(target).toHaveValue("input_image_2");
  await expect(target.locator("option", { hasText: "自动(按连线顺序)" })).toHaveCount(1);
  await target.selectOption({ label: "自动(按连线顺序)" });
  await expect(target).toHaveValue("");
});

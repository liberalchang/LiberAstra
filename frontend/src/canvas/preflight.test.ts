import assert from "node:assert/strict";
import { test } from "node:test";

import type { WorkflowPackOut } from "@/api/client";

import { validateCanvas } from "./preflight.ts";
import type { CanvasFlowNode } from "./types.ts";

const pack = {
  name: "image_edit",
  capability: "i2i",
  inputs: {
    image: { type: "image", required: true, label: "原图" },
    prompt: { type: "str", required: true },
  },
} as unknown as WorkflowPackOut;

function nodes(binding: string, withImageInput = true): CanvasFlowNode[] {
  const list: Record<string, unknown>[] = [
    {
      id: "fn",
      type: "function",
      position: { x: 320, y: 0 },
      data: {
        kind: "function",
        group: "g",
        pack: "image_edit",
        prompt: "换背景",
        bindings: { image: binding },
      },
    },
  ];
  if (withImageInput) {
    list.unshift({
      id: "img",
      type: "input",
      position: { x: 0, y: 0 },
      data: {
        kind: "input",
        mediaKind: "image",
        varName: "input_image_ref",
        assetId: 1,
      },
    });
  }
  return list.map((node) => node as unknown as CanvasFlowNode);
}

test("绑定变量不是直接上游时报错", () => {
  const issues = validateCanvas(nodes("input_image_ref"), [], [pack]);
  assert.equal(issues.length, 1);
  assert.match(issues[0].message, /不是上游节点/);
});

test("绑定变量有直接上游连线时通过", () => {
  const issues = validateCanvas(
    nodes("input_image_ref"),
    [{ id: "e", source: "img", target: "fn" }],
    [pack],
  );
  assert.deepEqual(issues, []);
});

test("绑定变量不存在时给出明确错误", () => {
  const issues = validateCanvas(nodes("input_image_ghost", false), [], [pack]);
  assert.equal(issues.length, 1);
  assert.match(issues[0].message, /不存在/);
});

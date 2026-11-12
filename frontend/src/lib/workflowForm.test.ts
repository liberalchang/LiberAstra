import assert from "node:assert/strict";
import { test } from "node:test";

import type { WorkflowAccelSpec, WorkflowInputSpec } from "@/api/client";
import { applyAccelPreset } from "./workflowForm.ts";

const accel: WorkflowAccelSpec = {
  node: "200",
  preset: { steps: 8, sampler_name: "euler" },
};

const inputs: Record<string, WorkflowInputSpec> = {
  steps: { node: "9", field: "inputs.steps", type: "int", default: 20 },
  sampler_name: {
    node: "17",
    field: "inputs.sampler_name",
    type: "str",
    default: "res_multistep",
  },
};

test("加速开启时缺失的 preset 参数补推荐值", () => {
  assert.deepEqual(applyAccelPreset({}, accel, inputs), {
    steps: "8",
    sampler_name: "euler",
  });
});

test("包默认值不算用户覆盖，开加速后落到 preset", () => {
  const values = { steps: "20", sampler_name: "res_multistep" };
  assert.deepEqual(applyAccelPreset(values, accel, inputs), {
    steps: "8",
    sampler_name: "euler",
  });
});

test("用户改成非默认值的参数保留", () => {
  const values = { steps: "12", sampler_name: "res_multistep" };
  assert.deepEqual(applyAccelPreset(values, accel, inputs), {
    steps: "12",
    sampler_name: "euler",
  });
});

test("没有 preset 的 LoRA 包不改参数", () => {
  const values = { steps: "20", sampler_name: "res_multistep" };
  assert.equal(applyAccelPreset(values, { node: "200" }, inputs), values);
});

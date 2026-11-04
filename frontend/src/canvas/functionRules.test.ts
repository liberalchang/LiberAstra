import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canApplyMenu,
  canApplyPack,
  canEditSpeechField,
  functionNodeTitle,
} from "./functionRules.ts";

test("已有功能的节点不能再次套用菜单", () => {
  const result = canApplyMenu(
    { kind: "function", presetId: "preset_t2i", subCapability: "t2i" },
    "preset_i2i",
  );
  assert.equal(result.ok, false);
  assert.match(result.reason ?? "", /创建时确定/);
});

test("空白功能节点允许首次绑定菜单", () => {
  assert.equal(
    canApplyMenu({ kind: "function" }, "preset_t2i").ok,
    true,
  );
});

test("空语音节点允许首次绑定菜单", () => {
  assert.equal(
    canApplyMenu({ kind: "speech", mode: "vc" }, "preset_vc", "vc").ok,
    true,
  );
});

test("语音节点不能套用不同模式的菜单", () => {
  const result = canApplyMenu({ kind: "speech", mode: "tts" }, "preset_vc", "vc");
  assert.equal(result.ok, false);
  assert.match(result.reason ?? "", /创建时确定/);
});

test("已经绑定执行目标的通用节点不能再套菜单", () => {
  assert.equal(
    canApplyMenu(
      { kind: "function", pack: "qwen_image_21_edit", targetType: "workflow" },
      "preset_t2i",
    ).ok,
    false,
  );
});

test("同一功能内允许切换到菜单允许的工作流包", () => {
  assert.equal(
    canApplyPack(
      { kind: "function", presetId: "preset_depth_gen", subCapability: "depth_gen" },
      "union_depth",
      ["union_depth", "posestudio"],
    ).ok,
    true,
  );
});

test("不允许跨功能换工作流包", () => {
  const result = canApplyPack(
    { kind: "function", presetId: "preset_depth_gen", subCapability: "depth_gen" },
    "qwen_image_21_edit",
    ["union_depth", "posestudio"],
  );
  assert.equal(result.ok, false);
  assert.match(result.reason ?? "", /不属于当前功能/);
});

test("通用节点允许绑定任意工作流包", () => {
  assert.equal(
    canApplyPack({ kind: "function" }, "any_workflow", []).ok,
    true,
  );
});

test("语音节点不能通过字段编辑切换 mode", () => {
  assert.equal(canEditSpeechField("mode"), false);
  assert.equal(canEditSpeechField("model"), true);
  assert.equal(canEditSpeechField("voiceRecordId"), true);
});

test("功能节目标题优先 presetTitle，其次 pack，再其次 targetId", () => {
  assert.equal(
    functionNodeTitle({
      presetTitle: "文生图",
      pack: "qwen_image_21",
      targetId: "model-a",
    }),
    "文生图",
  );
  assert.equal(
    functionNodeTitle({ pack: "qwen_image_21", targetId: "model-a" }),
    "qwen_image_21",
  );
  assert.equal(functionNodeTitle({ targetId: "model-a" }), "model-a");
  assert.equal(functionNodeTitle({}), "通用节点");
});

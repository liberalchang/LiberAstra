import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_TTS_TUNING,
  supportsEmotionModel,
  ttsOptions,
  tuningAt,
} from "./ttsTuning.ts";

test("高级参数关闭时不发送任何 TTS 选项", () => {
  assert.deepEqual(ttsOptions(DEFAULT_TTS_TUNING, true), {});
});

test("相关调节关闭时使用独立值", () => {
  assert.deepEqual(
    ttsOptions(
      {
        ...DEFAULT_TTS_TUNING,
        advanced: true,
        linked: false,
        speed: 0.9,
        exaggeration: 0.7,
        cfgWeight: 0.3,
      },
      true,
    ),
    { speed: 0.9, exaggeration: 0.7, cfg_weight: 0.3 },
  );
});

test("相关调节两端映射平静和激动", () => {
  assert.deepEqual(tuningAt(0), {
    preset: "calm",
    speed: 0.9,
    exaggeration: 0.35,
    cfgWeight: 0.55,
  });
  assert.deepEqual(tuningAt(1), {
    preset: "excited",
    speed: 1.15,
    exaggeration: 0.9,
    cfgWeight: 0.35,
  });
});

test("相关调节中间值在预设之间插值", () => {
  const value = tuningAt(0.5);
  assert.equal(value.preset, "natural");
  assert.ok(value.speed > 1 && value.speed < 1.05);
  assert.ok(value.exaggeration > 0.5 && value.exaggeration < 0.65);
});

test("Turbo/Nano 只发送语速", () => {
  assert.deepEqual(
    ttsOptions(
      {
        ...DEFAULT_TTS_TUNING,
        advanced: true,
        linked: true,
        expressiveness: 1,
        speed: 0.9,
      },
      false,
    ),
    { speed: 0.9 },
  );
  assert.equal(supportsEmotionModel("turbo"), false);
  assert.equal(supportsEmotionModel("nano"), false);
  assert.equal(supportsEmotionModel("multilingual_v3"), true);
});

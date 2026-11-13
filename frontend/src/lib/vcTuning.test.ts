import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_VC_TUNING,
  normalizeVcTuning,
  vcModelKind,
  vcOptions,
} from "./vcTuning.ts";

test("高级参数关闭时不发送任何 VC 选项", () => {
  assert.deepEqual(vcOptions({ ...DEFAULT_VC_TUNING, denoise: true }, "seed-vc"), {});
});

test("Chatterbox 发送通用后处理与分段参数", () => {
  const options = vcOptions(
    {
      ...DEFAULT_VC_TUNING,
      advanced: true,
      convertAll: true,
      segmentPadding: 0.2,
      mergeGap: 0.1,
      minSegment: 0.05,
      normalizeLoudness: true,
      targetLufs: -18,
      denoise: true,
      outputSampleRate: 44100,
      refStart: 1.5,
      refDuration: 8,
      seed: 42,
      diffusionSteps: 20,
    },
    "chatterbox",
  );
  assert.deepEqual(options, {
    convert_all: true,
    segment_padding: 0.2,
    merge_gap: 0.1,
    min_segment: 0.05,
    normalize_loudness: true,
    target_lufs: -18,
    denoise: true,
    output_sample_rate: 44100,
    ref_start: 1.5,
    ref_duration: 8,
  });
});

test("Seed-VC 追加生成参数", () => {
  const options = vcOptions(
    {
      ...DEFAULT_VC_TUNING,
      advanced: true,
      seed: 42,
      refMaxLen: 20,
      diffusionSteps: 20,
      inferenceCfgRate: 0.8,
      nQuantizers: 4,
      temperature: 1.1,
      lengthAdjust: 1.02,
      overlapFrameLen: 24,
      maxWindow: 18,
      context: 0.2,
      fade: 0.03,
    },
    "seed-vc",
  );
  assert.equal(options.seed, 42);
  assert.equal(options.ref_max_len, 20);
  assert.equal(options.diffusion_steps, 20);
  assert.equal(options.inference_cfg_rate, 0.8);
  assert.equal(options.n_quantizers, 4);
  assert.equal(options.temperature, 1.1);
  assert.equal(options.length_adjust, 1.02);
  assert.equal(options.overlap_frame_len, 24);
  assert.equal(options.max_window, 18);
  assert.equal(options.context, 0.2);
  assert.equal(options.fade, 0.03);
});

test("Chatterbox 不发送 Seed-VC 专属参数", () => {
  const options = vcOptions(
    {
      ...DEFAULT_VC_TUNING,
      advanced: true,
      seed: 1,
      diffusionSteps: 12,
      refMaxLen: 20,
    },
    "chatterbox",
  );
  assert.equal("seed" in options, false);
  assert.equal("diffusion_steps" in options, false);
  assert.equal("ref_max_len" in options, false);
  assert.equal("segment_padding" in options, true);
});

test("响度目标仅在归一开启时发送", () => {
  const options = vcOptions(
    { ...DEFAULT_VC_TUNING, advanced: true, targetLufs: -20 },
    "chatterbox",
  );
  assert.equal("target_lufs" in options, false);
});

test("采样率 0 不发送", () => {
  const options = vcOptions(
    { ...DEFAULT_VC_TUNING, advanced: true, outputSampleRate: 0 },
    "chatterbox",
  );
  assert.equal("output_sample_rate" in options, false);
});

test("附加 JSON 合并并覆盖显式值", () => {
  const options = vcOptions(
    {
      ...DEFAULT_VC_TUNING,
      advanced: true,
      denoise: false,
      extraJson: '{"denoise": true, "max_window": 12}',
    },
    "seed-vc",
  );
  assert.equal(options.denoise, true);
  assert.equal(options.max_window, 12);
});

test("归一化钳制越界值", () => {
  const tuning = normalizeVcTuning({
    advanced: true,
    diffusionSteps: 999,
    inferenceCfgRate: -1,
    outputSampleRate: 999999,
    seed: -5,
  });
  assert.equal(tuning.diffusionSteps, 50);
  assert.equal(tuning.inferenceCfgRate, 0);
  assert.equal(tuning.outputSampleRate, 192000);
  assert.equal(tuning.seed, 0);
});

test("模型识别", () => {
  assert.equal(vcModelKind("seed-vc"), "seedvc");
  assert.equal(vcModelKind("chatterbox"), "chatterbox");
  assert.equal(vcModelKind(""), "chatterbox");
});

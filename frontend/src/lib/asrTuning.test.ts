import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ASR_TUNING,
  asrModelKind,
  asrOptions,
  normalizeAsrTuning,
} from "./asrTuning.ts";

test("高级参数关闭时不发送任何 ASR 选项", () => {
  assert.deepEqual(asrOptions({ ...DEFAULT_ASR_TUNING, vad: true }, "large-v3"), {});
});

test("Whisper 映射时间戳、VAD 与解码参数", () => {
  const options = asrOptions(
    {
      ...DEFAULT_ASR_TUNING,
      advanced: true,
      timestamps: "word",
      vad: true,
      task: "translate",
      beamSize: 8,
      bestOf: 6,
      temperature: "0, 0.2, 0.4",
      noSpeechThreshold: 0.4,
      conditionOnPreviousText: false,
      initialPrompt: "人名：张三",
      hotwords: "LiberAstra 语音",
    },
    "large-v3-turbo",
  );
  assert.equal(options.timestamps, "word");
  assert.equal(options.vad_filter, true);
  assert.equal(options.task, "translate");
  assert.equal(options.beam_size, 8);
  assert.equal(options.best_of, 6);
  assert.deepEqual(options.temperature, [0, 0.2, 0.4]);
  assert.equal(options.no_speech_threshold, 0.4);
  assert.equal(options.condition_on_previous_text, false);
  assert.equal(options.initial_prompt, "人名：张三");
  assert.equal(options.hotwords, "LiberAstra 语音");
});

test("Qwen 过滤 Whisper 专属参数并保留批大小", () => {
  const options = asrOptions(
    {
      ...DEFAULT_ASR_TUNING,
      advanced: true,
      task: "translate",
      vad: true,
      beamSize: 8,
      hotwords: "热词",
      qwenBatchSize: 8,
    },
    "qwen3-asr-1.7b",
  );
  assert.deepEqual(options, {
    timestamps: "segment",
    max_inference_batch_size: 8,
  });
});

test("空白模型按 Whisper 规则处理", () => {
  assert.equal(asrModelKind(""), "whisper");
  assert.equal(asrModelKind("qwen3-asr-1.7b"), "qwen");
  const options = asrOptions(
    { ...DEFAULT_ASR_TUNING, advanced: true, vad: true },
    "",
  );
  assert.equal(options.vad_filter, true);
});

test("附加 JSON 合并并覆盖显式值", () => {
  const options = asrOptions(
    {
      ...DEFAULT_ASR_TUNING,
      advanced: true,
      beamSize: 5,
      extraJson: '{"beam_size": 9, "suppress_blank": false}',
    },
    "large-v3",
  );
  assert.equal(options.beam_size, 9);
  assert.equal(options.suppress_blank, false);
});

test("非法附加 JSON 被忽略", () => {
  const options = asrOptions(
    { ...DEFAULT_ASR_TUNING, advanced: true, extraJson: "{oops" },
    "large-v3",
  );
  assert.equal("suppress_blank" in options, false);
  assert.equal(options.beam_size, DEFAULT_ASR_TUNING.beamSize);
});

test("归一化钳制越界值并忽略非法类型", () => {
  const tuning = normalizeAsrTuning({
    advanced: true,
    beamSize: 999,
    noSpeechThreshold: 5,
    qwenBatchSize: 0,
    timestamps: "bad",
    temperature: "0.2, nope, 0.8",
  });
  assert.equal(tuning.beamSize, 10);
  assert.equal(tuning.noSpeechThreshold, 1);
  assert.equal(tuning.qwenBatchSize, 1);
  assert.equal(tuning.timestamps, "segment");
  assert.equal(tuning.temperature, "0.2, 0.8");
});

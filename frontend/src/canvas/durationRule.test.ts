import assert from "node:assert/strict";
import test from "node:test";

import { durationRuleFor } from "./durationRule.ts";

test("数字人口播时长跟随音频，忽略 length", () => {
  const rule = durationRuleFor("avatar", false);
  assert.equal(rule.mode, "audio");
  assert.equal(rule.lengthIgnored, true);
  assert.equal(rule.totalLimit, false);
  assert.match(rule.note, /音频/);
});

test("动作迁移时长跟随参考视频，忽略 length", () => {
  const rule = durationRuleFor("motion", false);
  assert.equal(rule.mode, "source_video");
  assert.equal(rule.lengthIgnored, true);
  assert.equal(rule.totalLimit, false);
  assert.match(rule.note, /参考视频/);
});

test("连续生成用 clips_json，按片段时长控制", () => {
  const rule = durationRuleFor("i2v", true);
  assert.equal(rule.mode, "clips");
  assert.equal(rule.lengthIgnored, true);
  assert.equal(rule.totalLimit, false);
  assert.match(rule.note, /clips_json/);
});

test("普通视频节点手动 length 只是单段上限", () => {
  for (const capability of ["t2v", "i2v"]) {
    const rule = durationRuleFor(capability, false);
    assert.equal(rule.mode, "manual");
    assert.equal(rule.lengthIgnored, false);
    assert.equal(rule.totalLimit, false);
    assert.match(rule.note, /单段/);
    assert.match(rule.note, /参考音频/);
  }
});

test("修复放大和视频理解跟随输入视频", () => {
  for (const capability of ["upscale", "v2v", "video_upscale", "analysis"]) {
    const rule = durationRuleFor(capability, false);
    assert.equal(rule.mode, "source");
    assert.equal(rule.lengthIgnored, true);
  }
});

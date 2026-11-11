import assert from "node:assert/strict";
import { test } from "node:test";

import { createDefaultNodeData, normalizeNodeData } from "./types.ts";

test("视频拼接节点默认 60ms 接缝淡化", () => {
  const data = createDefaultNodeData("concat", "video");
  assert.equal(data.kind, "concat");
  if (data.kind === "concat") assert.equal(data.audioFadeMs, 60);

  const fallback = createDefaultNodeData("concat", undefined);
  if (fallback.kind === "concat") {
    assert.equal(fallback.mediaKind, "video");
    assert.equal(fallback.audioFadeMs, 60);
  }
});

test("已有画布没有 audioFadeMs 时补 60，超出范围时夹到 0–200", () => {
  const fallback = normalizeNodeData("concat", {
    mediaKind: "video",
    order: [],
  });
  if (fallback.kind === "concat") assert.equal(fallback.audioFadeMs, 60);

  const high = normalizeNodeData("concat", {
    mediaKind: "video",
    order: [],
    audioFadeMs: 999,
  });
  if (high.kind === "concat") assert.equal(high.audioFadeMs, 200);

  const audio = normalizeNodeData("concat", {
    mediaKind: "audio",
    order: [],
  });
  if (audio.kind === "concat") assert.equal(audio.audioFadeMs, undefined);
});

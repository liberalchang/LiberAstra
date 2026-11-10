import assert from "node:assert/strict";
import { test } from "node:test";

import { secondsToFrames, snapFramesCeil } from "./duration.ts";

const H3 = { align_base: 17, align_offset: 5 };

test("17n+5 按 ceil 向上吸附", () => {
  assert.equal(secondsToFrames(9, 24, H3), 226);
  assert.equal(secondsToFrames(10, 24, H3), 243);
  assert.equal(secondsToFrames(15, 24, H3), 362);
});

test("无对齐规则时向上取整", () => {
  assert.equal(secondsToFrames(1.1, 24), 27);
  assert.equal(snapFramesCeil(26.1), 27);
});

test("低于最小时吸到最小合法帧", () => {
  assert.equal(snapFramesCeil(72, H3), 73);
});

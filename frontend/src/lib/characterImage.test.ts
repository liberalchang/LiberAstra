import assert from "node:assert/strict";
import test from "node:test";

import { characterImageUrl } from "./characterImage.ts";

test("角色图 URL 带图片路径版本", () => {
  assert.equal(
    characterImageUrl(1, "front", "characters/abc.png"),
    "/api/v1/characters/1/image/front?v=characters%2Fabc.png",
  );
});

test("没有版本时保持原 URL", () => {
  assert.equal(characterImageUrl(1, "front"), "/api/v1/characters/1/image/front");
  assert.equal(characterImageUrl(1, "front", ""), "/api/v1/characters/1/image/front");
});

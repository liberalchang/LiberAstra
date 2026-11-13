import assert from "node:assert/strict";
import test from "node:test";

import { discardableNodeIds } from "./discard.ts";

test("未执行的草稿节点可丢弃，即使还连着线", () => {
  const result = discardableNodeIds(
    [
      { id: "a", data: { run: { status: "idle", jobId: null, assetIds: [] } } },
      { id: "b", data: {} },
    ],
    [{ source: "a", target: "b" }],
    ["a", "b"],
  );
  assert.deepEqual(result.discardable, ["a", "b"]);
  assert.deepEqual(result.blocked, []);
  assert.deepEqual(result.missing, []);
});

test("有执行记录或产物的节点不会被丢弃", () => {
  const result = discardableNodeIds(
    [
      { id: "job", data: { run: { status: "running", jobId: "j1" } } },
      { id: "asset", data: { run: { status: "idle", assetIds: [3] } } },
      { id: "done", data: { run: { status: "succeeded" } } },
    ],
    [],
    ["job", "asset", "done"],
  );
  assert.deepEqual(result.discardable, []);
  assert.deepEqual(result.blocked.map((item) => item.id), ["job", "asset", "done"]);
});

test("不存在的节点单独返回", () => {
  const result = discardableNodeIds([{ id: "a", data: {} }], [], ["a", "ghost"]);
  assert.deepEqual(result.discardable, ["a"]);
  assert.deepEqual(result.missing, ["ghost"]);
});

test("重复 id 只处理一次", () => {
  const result = discardableNodeIds([{ id: "a", data: {} }], [], ["a", "a"]);
  assert.deepEqual(result.discardable, ["a"]);
});

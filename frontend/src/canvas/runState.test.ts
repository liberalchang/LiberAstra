import assert from "node:assert/strict";
import { test } from "node:test";

import { hasActiveRun, settleStaleRuns } from "./runState.ts";
import type { CanvasFlowNode } from "./types.ts";

function node(id: string, status: string): CanvasFlowNode {
  return {
    id,
    type: "function",
    position: { x: 0, y: 0 },
    data: { kind: "function", varName: id, run: { status } },
  } as unknown as CanvasFlowNode;
}

test("plan 或 node_runs 有 pending/running 时认为运行中", () => {
  assert.equal(hasActiveRun([{ status: "pending" }], []), true);
  assert.equal(hasActiveRun([{ status: "succeeded" }], [{ status: "running" }]), true);
  assert.equal(
    hasActiveRun(
      [{ status: "succeeded" }, { status: "canceled" }],
      [{ status: "failed" }],
    ),
    false,
  );
});

test("后端已无活动任务时把本地遗留的 pending/running 归为 canceled", () => {
  const nodes = [node("pending", "pending"), node("running", "running"), node("done", "succeeded")];
  const settled = settleStaleRuns(nodes, false);
  assert.deepEqual(
    settled.map((item) => item.data.run.status),
    ["canceled", "canceled", "succeeded"],
  );
});

test("仍有活动任务时不清理本地状态", () => {
  const nodes = [node("pending", "pending")];
  assert.equal(settleStaleRuns(nodes, true), nodes);
});

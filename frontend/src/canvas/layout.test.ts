import assert from "node:assert/strict";
import { test } from "node:test";

import type { Edge } from "@xyflow/react";

import { layeredLayout } from "./layout.ts";
import type { CanvasFlowNode } from "./types.ts";

function node(
  id: string,
  x: number,
  y: number,
  kind: "input" | "function" | "concat" = "function",
): CanvasFlowNode {
  return {
    id,
    type: kind,
    position: { x, y },
    data: { kind, mediaKind: "image", varName: id },
  } as unknown as CanvasFlowNode;
}

function edge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target };
}

function orderByY(
  positions: Map<string, { x: number; y: number }>,
  ids: string[],
): string[] {
  return [...ids].sort(
    (a, b) => (positions.get(a)?.y ?? 0) - (positions.get(b)?.y ?? 0),
  );
}

test("整理画布保持同列兄弟节点原来的上下顺序", () => {
  const nodes = [
    node("t1", 100, -20, "input"),
    node("t2", 100, 300, "input"),
    node("t3", 100, 620, "input"),
    node("t4", 100, 940, "input"),
    node("kf1_1", 420, -20),
    node("kf1_2", 420, 300),
    node("kf2_1", 420, 620),
    node("kf2_2", 420, 940),
    node("concat", 900, 120, "concat"),
    node("video", 1400, 120),
  ];
  const edges = [
    edge("t1", "kf1_1"),
    edge("t2", "kf2_1"),
    edge("t3", "kf1_2"),
    edge("t4", "kf2_2"),
    edge("kf1_1", "concat"),
    edge("kf2_1", "concat"),
    edge("kf1_2", "concat"),
    edge("kf2_2", "concat"),
    edge("concat", "video"),
  ];

  const positions = layeredLayout(nodes, edges);
  const order = orderByY(positions, [
    "kf1_1",
    "kf1_2",
    "kf2_1",
    "kf2_2",
  ]);

  assert.deepEqual(order, ["kf1_1", "kf1_2", "kf2_1", "kf2_2"]);
  assert.ok(positions.get("t1")!.x < positions.get("kf1_1")!.x);
  assert.ok(positions.get("kf1_1")!.x < positions.get("concat")!.x);
  assert.ok(positions.get("concat")!.x < positions.get("video")!.x);
});

test("四个分镜的首尾帧按整理前的顺序从上往下排", () => {
  const nodes: CanvasFlowNode[] = [];
  const edges: Edge[] = [];
  const ids = [
    "kf1_1",
    "kf1_2",
    "kf2_1",
    "kf2_2",
    "kf3_1",
    "kf3_2",
    "kf4_1",
    "kf4_2",
  ];
  ids.forEach((id, index) => {
    nodes.push(node(id, 420, index * 300));
    nodes.push(node(`text_${id}`, 100, index * 300, "input"));
    edges.push(edge(`text_${id}`, id));
  });
  nodes.push(node("concat", 900, 120, "concat"));
  // 导演技能先连全部首帧，再连全部尾帧。
  for (const id of ids.filter((item) => item.endsWith("_1"))) {
    edges.push(edge(id, "concat"));
  }
  for (const id of ids.filter((item) => item.endsWith("_2"))) {
    edges.push(edge(id, "concat"));
  }

  const positions = layeredLayout(nodes, edges);
  assert.deepEqual(orderByY(positions, ids), ids);
});

test("没有连线的输入节点仍然排在依赖图下方", () => {
  const nodes = [
    node("text", 100, 0, "input"),
    node("kf", 420, 0),
    node("concat", 900, 0, "concat"),
    node("character", 100, 400, "input"),
    node("script", 420, 400, "input"),
  ];
  const edges = [edge("text", "kf"), edge("kf", "concat")];

  const positions = layeredLayout(nodes, edges);
  const linkedBottom = Math.max(
    positions.get("text")!.y,
    positions.get("kf")!.y,
    positions.get("concat")!.y,
  );
  assert.ok(positions.get("character")!.y > linkedBottom);
  assert.ok(positions.get("script")!.y > linkedBottom);
});

test("再次整理不会翻转已经排好的顺序", () => {
  const nodes = [
    node("t1", 100, 0, "input"),
    node("t2", 100, 300, "input"),
    node("kf1", 420, 0),
    node("kf2", 420, 300),
    node("concat", 900, 0, "concat"),
  ];
  const edges = [
    edge("t1", "kf1"),
    edge("t2", "kf2"),
    edge("kf1", "concat"),
    edge("kf2", "concat"),
  ];

  const first = layeredLayout(nodes, edges);
  const nextNodes = nodes.map((item) => ({
    ...item,
    position: first.get(item.id)!,
  }));
  const second = layeredLayout(nextNodes, edges);
  assert.deepEqual(orderByY(second, ["kf1", "kf2"]), ["kf1", "kf2"]);
});

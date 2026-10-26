/** 整理画布：分层 DAG 布局（topo 层 → x，层内序号 → y），不引 dagre。 */
import type { Edge } from "@xyflow/react";

import type { CanvasFlowNode } from "@/canvas/types";

const X_GAP = 320;
const Y_GAP = 200;

/** 返回 id → 新位置；孤立节点排在最后一层之后。 */
export function layeredLayout(
  nodes: CanvasFlowNode[],
  edges: Edge[],
): Map<string, { x: number; y: number }> {
  const ids = nodes.map((n) => n.id);
  const indegree = new Map<string, number>(ids.map((id) => [id, 0]));
  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    if (!indegree.has(e.source) || !indegree.has(e.target)) continue;
    indegree.set(e.target, (indegree.get(e.target) ?? 0) + 1);
    outgoing.set(e.source, [...(outgoing.get(e.source) ?? []), e.target]);
  }

  // Kahn 分层：layer[n] = 最长入链长度
  const layer = new Map<string, number>(ids.map((id) => [id, 0]));
  let queue = ids.filter((id) => (indegree.get(id) ?? 0) === 0);
  const visited = new Set<string>();
  while (queue.length) {
    const next: string[] = [];
    for (const id of queue) {
      if (visited.has(id)) continue;
      visited.add(id);
      for (const target of outgoing.get(id) ?? []) {
        layer.set(target, Math.max(layer.get(target) ?? 0, (layer.get(id) ?? 0) + 1));
        const deg = (indegree.get(target) ?? 1) - 1;
        indegree.set(target, deg);
        if (deg <= 0) next.push(target);
      }
    }
    queue = next;
  }

  // 按层分列，层内按当前 y 排序保持稳定
  const byLayer = new Map<number, CanvasFlowNode[]>();
  const sorted = [...nodes].sort((a, b) => a.position.y - b.position.y);
  for (const node of sorted) {
    const l = layer.get(node.id) ?? 0;
    byLayer.set(l, [...(byLayer.get(l) ?? []), node]);
  }

  const positions = new Map<string, { x: number; y: number }>();
  const maxPerCol = Math.max(...[...byLayer.values()].map((col) => col.length), 1);
  for (const [l, col] of byLayer) {
    const offsetY = ((maxPerCol - col.length) * Y_GAP) / 2;
    col.forEach((node, index) => {
      positions.set(node.id, { x: l * X_GAP, y: offsetY + index * Y_GAP });
    });
  }
  return positions;
}

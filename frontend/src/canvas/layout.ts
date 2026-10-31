/** 整理画布：按连通块用 dagre 分层排布。dagre 用网络单纯形（network simplex）让输入靠近消费者。 */
import { Graph, layout as dagreLayout } from "@dagrejs/dagre";
import type { Edge } from "@xyflow/react";

import type { CanvasFlowNode } from "@/canvas/types";

const NODE_W = 260;
const NODE_SEP = 40;
const RANK_SEP = 100;
const EDGE_SEP = 20;
const BAND_GAP = 120;
const GRID_COLS = 4;
const GRID_GAP = 40;

type Box = { id: string; x: number; y: number; w: number; h: number };

function nodeSize(node: CanvasFlowNode): { w: number; h: number } {
  const w = node.measured?.width;
  const h = node.measured?.height;
  if (w && h && w > 0 && h > 0) return { w, h };
  if (node.data.kind === "input") {
    return node.data.mediaKind === "text" ? { w: NODE_W, h: 100 } : { w: NODE_W, h: 160 };
  }
  return { w: NODE_W, h: 230 };
}

/** 无向连通块。孤立节点（没有任何连线）不在这里。 */
function connectedGroups(nodes: CanvasFlowNode[], edges: Edge[]): CanvasFlowNode[][] {
  const adj = new Map<string, string[]>(nodes.map((n) => [n.id, []]));
  const linked = new Set<string>();
  for (const edge of edges) {
    if (!adj.has(edge.source) || !adj.has(edge.target) || edge.source === edge.target) continue;
    adj.get(edge.source)!.push(edge.target);
    adj.get(edge.target)!.push(edge.source);
    linked.add(edge.source);
    linked.add(edge.target);
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const seen = new Set<string>();
  const groups: CanvasFlowNode[][] = [];
  const ordered = [...nodes].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);
  for (const start of ordered) {
    if (!linked.has(start.id) || seen.has(start.id)) continue;
    const group: CanvasFlowNode[] = [];
    const stack = [start.id];
    seen.add(start.id);
    while (stack.length) {
      const id = stack.pop()!;
      const node = byId.get(id);
      if (node) group.push(node);
      for (const next of adj.get(id) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        stack.push(next);
      }
    }
    groups.push(group);
  }
  groups.sort(
    (a, b) =>
      Math.min(...a.map((n) => n.position.y)) - Math.min(...b.map((n) => n.position.y)) ||
      Math.min(...a.map((n) => n.position.x)) - Math.min(...b.map((n) => n.position.x)),
  );
  return groups;
}

function layoutGroup(group: CanvasFlowNode[], edges: Edge[]): Box[] {
  const graph = new Graph({ directed: true });
  graph.setGraph({
    rankdir: "LR",
    ranker: "network-simplex",
    nodesep: NODE_SEP,
    ranksep: RANK_SEP,
    edgesep: EDGE_SEP,
    marginx: 0,
    marginy: 0,
    acyclicer: "greedy",
  });
  graph.setDefaultEdgeLabel(() => ({}));

  const sorted = [...group].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);
  const sizes = new Map<string, { w: number; h: number }>();
  for (const node of sorted) {
    const size = nodeSize(node);
    sizes.set(node.id, size);
    graph.setNode(node.id, { width: size.w, height: size.h });
  }
  const ids = new Set(sorted.map((n) => n.id));
  const seenEdge = new Set<string>();
  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target) continue;
    const key = `${edge.source}\0${edge.target}`;
    if (seenEdge.has(key)) continue;
    seenEdge.add(key);
    graph.setEdge(edge.source, edge.target);
  }
  dagreLayout(graph);

  const boxes: Box[] = sorted.map((node) => {
    const label = graph.node(node.id);
    const size = sizes.get(node.id)!;
    return {
      id: node.id,
      x: label.x - size.w / 2,
      y: label.y - size.h / 2,
      w: size.w,
      h: size.h,
    };
  });
  pullInputsCloser(boxes, edges, ids);
  return boxes;
}

/** 没有上游的输入若离消费者超过一列，收到消费者左边那一列。
 * dagre 的 rank 会把长边拆成虚拟列，所以用水平间距判断，不用 rank 相减。
 */
function pullInputsCloser(boxes: Box[], edges: Edge[], ids: Set<string>): void {
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, number>([...ids].map((id) => [id, 0]));
  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target) continue;
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge.target]);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  }
  const byId = new Map(boxes.map((box) => [box.id, box]));
  const touched = new Set<string>();
  for (const box of boxes) {
    if ((incoming.get(box.id) ?? 0) > 0) continue;
    const targets = (outgoing.get(box.id) ?? []).map((id) => byId.get(id)).filter((n): n is Box => !!n);
    if (!targets.length) continue;
    const succLeft = Math.min(...targets.map((n) => n.x));
    const gap = succLeft - (box.x + box.w);
    if (gap <= RANK_SEP + NODE_W * 0.6) continue;
    const adjacent = boxes.filter(
      (n) => n.id !== box.id && n.x + n.w <= succLeft + 1 && succLeft - (n.x + n.w) <= RANK_SEP + 40,
    );
    box.x = adjacent.length ? Math.min(...adjacent.map((n) => n.x)) : succLeft - RANK_SEP - box.w;
    const mid = targets.reduce((sum, n) => sum + n.y + n.h / 2, 0) / targets.length;
    box.y = mid - box.h / 2;
    touched.add(box.id);
    for (const peer of adjacent) touched.add(peer.id);
  }
  if (!touched.size) return;
  const columns: Box[][] = [];
  for (const box of [...boxes].sort((a, b) => a.x - b.x)) {
    const column = columns.find((col) => Math.abs(col[0].x - box.x) < 20);
    if (column) column.push(box);
    else columns.push([box]);
  }
  for (const column of columns) {
    if (!column.some((box) => touched.has(box.id))) continue;
    column.sort((a, b) => a.y - b.y);
    for (let i = 1; i < column.length; i++) {
      const minY = column[i - 1].y + column[i - 1].h + NODE_SEP;
      if (column[i].y < minY) column[i].y = minY;
    }
  }
}

function placeBand(boxes: Box[], positions: Map<string, { x: number; y: number }>, top: number): number {
  if (!boxes.length) return top;
  const minX = Math.min(...boxes.map((box) => box.x));
  const minY = Math.min(...boxes.map((box) => box.y));
  for (const box of boxes) {
    positions.set(box.id, { x: box.x - minX, y: box.y - minY + top });
  }
  const bottom = Math.max(...boxes.map((box) => box.y - minY + top + box.h));
  return bottom + BAND_GAP;
}

function placeIsolated(
  nodes: CanvasFlowNode[],
  positions: Map<string, { x: number; y: number }>,
  top: number,
): void {
  let y = top;
  for (let i = 0; i < nodes.length; i += GRID_COLS) {
    const row = nodes.slice(i, i + GRID_COLS);
    let x = 0;
    let rowH = 0;
    for (const node of row) {
      const size = nodeSize(node);
      positions.set(node.id, { x, y });
      x += size.w + GRID_GAP;
      rowH = Math.max(rowH, size.h);
    }
    y += rowH + GRID_GAP;
  }
}

/** 返回 id → 新位置。互不相连的链各自成块，孤立节点排在最后。 */
export function layeredLayout(
  nodes: CanvasFlowNode[],
  edges: Edge[],
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (!nodes.length) return positions;

  const linked = new Set<string>();
  for (const edge of edges) {
    if (edge.source === edge.target) continue;
    if (!nodes.some((n) => n.id === edge.source) || !nodes.some((n) => n.id === edge.target)) continue;
    linked.add(edge.source);
    linked.add(edge.target);
  }
  const groups = connectedGroups(nodes, edges);
  let top = 0;
  for (const group of groups) {
    top = placeBand(layoutGroup(group, edges), positions, top);
  }
  const isolated = nodes
    .filter((node) => !linked.has(node.id))
    .sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);
  placeIsolated(isolated, positions, groups.length ? top : 0);
  return positions;
}

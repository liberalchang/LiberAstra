/** 连线校验：自环/重复边/环/合成节点媒体类型兼容（open-canvas validation.ts 的精简移植）。
 * 包的 manifest 前端不预载，功能节点的媒体输入匹配在执行时由后端校验并给出中文错误。
 */
import type { Connection, Edge } from "@xyflow/react";

import type { CanvasFlowNode } from "@/canvas/types";
import { nodeOutputKind } from "@/canvas/types";

/** 从 source 沿现有边正向 DFS，能到达 target 说明 source→target 新边会成环。 */
export function wouldCreateCycle(edges: Edge[], source: string, target: string): boolean {
  const bySource = new Map<string, string[]>();
  for (const e of edges) {
    const list = bySource.get(e.source) ?? [];
    list.push(e.target);
    bySource.set(e.source, list);
  }
  const seen = new Set<string>();
  const queue = [target];
  // 新边 source→target 成环 ⟺ 现有图中 target 已能到达 source
  while (queue.length) {
    const nid = queue.pop()!;
    if (nid === source) return true;
    if (seen.has(nid)) continue;
    seen.add(nid);
    queue.push(...(bySource.get(nid) ?? []));
  }
  return false;
}

export function hasEdge(edges: Edge[], source: string, target: string): boolean {
  return edges.some((e) => e.source === source && e.target === target);
}

export type ConnectReject =
  | "self"
  | "duplicate"
  | "cycle"
  | "input-no-inlet"
  | "concat-kind"
  | "missing-endpoint";

export function checkConnection(
  nodes: CanvasFlowNode[],
  edges: Edge[],
  conn: Connection,
): { ok: true } | { ok: false; reason: ConnectReject } {
  const { source, target } = conn;
  if (!source || !target) return { ok: false, reason: "missing-endpoint" };
  if (source === target) return { ok: false, reason: "self" };
  const sourceNode = nodes.find((n) => n.id === source);
  const targetNode = nodes.find((n) => n.id === target);
  if (!sourceNode || !targetNode) return { ok: false, reason: "missing-endpoint" };
  if (targetNode.data.kind === "input") return { ok: false, reason: "input-no-inlet" };
  if (hasEdge(edges, source, target)) return { ok: false, reason: "duplicate" };
  if (wouldCreateCycle(edges, source, target)) return { ok: false, reason: "cycle" };
  // 合成节点只收同类型媒体（产物类型未知的节点也拒绝,避免执行期才报错）
  if (targetNode.data.kind === "concat") {
    const out = nodeOutputKind(sourceNode);
    if (out !== targetNode.data.mediaKind) return { ok: false, reason: "concat-kind" };
  }
  // 语音转文字收音频或视频
  if (targetNode.data.kind === "speech" && targetNode.data.mode === "asr") {
    const out = nodeOutputKind(sourceNode);
    if (out !== "audio" && out !== "video") return { ok: false, reason: "concat-kind" };
  }
  return { ok: true };
}

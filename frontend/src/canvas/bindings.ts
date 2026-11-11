/** 槽位绑定到画布节点的映射；绑定只选槽，媒体依赖仍走真实连线。 */
import { nodeOutputKind, type CanvasFlowNode, type MediaKind } from "./types.ts";

export interface BindingSource {
  varName: string;
  node: CanvasFlowNode | null;
  mediaKind: MediaKind | null;
}

export function findNodeByVar(
  nodes: CanvasFlowNode[],
  varName: string,
): CanvasFlowNode | null {
  const name = varName.trim();
  if (!name) return null;
  return (
    nodes.find(
      (node) => String((node.data as { varName?: string }).varName ?? "").trim() === name,
    ) ?? null
  );
}

/** 按绑定值去重，返回每个变量对应的节点与输出类型；文本变量 mediaKind 为 null。 */
export function bindingSources(
  nodes: CanvasFlowNode[],
  bindings: Record<string, string> | undefined,
): BindingSource[] {
  const seen = new Set<string>();
  const out: BindingSource[] = [];
  for (const raw of Object.values(bindings ?? {})) {
    const varName = String(raw ?? "").trim();
    if (!varName || seen.has(varName)) continue;
    seen.add(varName);
    const node = findNodeByVar(nodes, varName);
    out.push({ varName, node, mediaKind: node ? nodeOutputKind(node) : null });
  }
  return out;
}

export interface MissingBindingEdge {
  source: string;
  target: string;
  varName: string;
  slot: string;
}

/** 媒体槽已绑定但缺少直接上游连线。文本绑定走 {{var}}，不需要边。 */
export function missingBindingEdges(
  nodes: CanvasFlowNode[],
  edges: { source: string; target: string }[],
): MissingBindingEdge[] {
  const edgeKeys = new Set(edges.map((edge) => `${edge.source}\u0000${edge.target}`));
  const seen = new Set<string>();
  const out: MissingBindingEdge[] = [];
  for (const node of nodes) {
    if (node.data.kind !== "function") continue;
    const bindings = (node.data as { bindings?: Record<string, string> }).bindings ?? {};
    for (const [slot, raw] of Object.entries(bindings)) {
      const varName = String(raw ?? "").trim();
      if (!varName) continue;
      const source = findNodeByVar(nodes, varName);
      if (!source || !nodeOutputKind(source)) continue;
      const key = `${source.id}\u0000${node.id}`;
      if (edgeKeys.has(key) || seen.has(key)) continue;
      seen.add(key);
      out.push({ source: source.id, target: node.id, varName, slot });
    }
  }
  return out;
}

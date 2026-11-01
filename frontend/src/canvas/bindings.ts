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

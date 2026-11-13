interface DiscardNode {
  id: string;
  data?: Record<string, unknown> | null;
}

export interface DiscardBlocked {
  id: string;
  reason: string;
}

export interface DiscardResult {
  discardable: string[];
  blocked: DiscardBlocked[];
  missing: string[];
}

function hasRun(node: DiscardNode): string | null {
  const run = node.data?.run;
  if (!run || typeof run !== "object") return null;
  const data = run as { status?: unknown; jobId?: unknown; assetIds?: unknown };
  const status = typeof data.status === "string" ? data.status : "idle";
  if (status !== "idle") return `已有执行记录（${status}）`;
  if (data.jobId) return "已有执行任务";
  if (Array.isArray(data.assetIds) && data.assetIds.length > 0) return "已有产物";
  return null;
}

export function discardableNodeIds(
  nodes: DiscardNode[],
  _edges: { source: string; target: string }[],
  ids: string[],
): DiscardResult {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  const result: DiscardResult = { discardable: [], blocked: [], missing: [] };
  for (const id of ids) {
    if (seen.has(id)) continue;
    seen.add(id);
    const node = byId.get(id);
    if (!node) {
      result.missing.push(id);
      continue;
    }
    const reason = hasRun(node);
    if (reason) {
      result.blocked.push({ id, reason });
    } else {
      result.discardable.push(id);
    }
  }
  return result;
}

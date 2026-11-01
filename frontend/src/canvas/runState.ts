/** 画布运行状态归并：以后端 plan / node_runs 为准，清理本地遗留的 pending。 */
import type { CanvasFlowNode } from "./types.ts";

interface RunLike {
  status: string;
}

export function hasActiveRun(
  plan: RunLike[] | undefined,
  runs: RunLike[],
): boolean {
  return [...(plan ?? []), ...runs].some(
    (item) => item.status === "pending" || item.status === "running",
  );
}

/** 后端已经没有任何活动任务时，把本地残留的 pending/running 节点归为 canceled。 */
export function settleStaleRuns(
  nodes: CanvasFlowNode[],
  active: boolean,
): CanvasFlowNode[] {
  if (active) return nodes;
  return nodes.map((node) => {
    if (!["pending", "running"].includes(node.data.run.status)) return node;
    return {
      ...node,
      data: {
        ...node.data,
        run: { ...node.data.run, status: "canceled" as const },
      },
    } as CanvasFlowNode;
  });
}

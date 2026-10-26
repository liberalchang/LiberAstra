/** 画布编辑器状态（zustand）：节点/边/视口/脏标记/执行状态。
 *
 * 序列化：graph 存 React Flow 结构，run 状态存在 node.data.run 一并落库
 * （服务端只用 nodes/edges/viewport，不解释 data）。
 */
import {
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
  type Viewport,
} from "@xyflow/react";
import { create } from "zustand";

import type { CanvasGraph, CanvasNodeRunOut, CanvasOut } from "@/api/client";
import {
  createDefaultNodeData,
  idleRun,
  normalizeNodeData,
  type CanvasFlowNode,
  type CanvasNodeKind,
  type MediaKind,
  type NodeRunState,
} from "@/canvas/types";
import { checkConnection } from "@/canvas/validation";

let seq = 0;
const newNodeId = (kind: string) => `${kind}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

/** 变量名默认填充:取该前缀(input_text / output_image …)现有最大序号 +1,删节点不回填。 */
export function nextVarName(nodes: CanvasFlowNode[], prefix: string): string {
  let max = 0;
  const re = new RegExp(`^${prefix}_(\\d+)$`);
  for (const n of nodes) {
    const v = (n.data as { varName?: string }).varName ?? "";
    const m = re.exec(v);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return `${prefix}_${max + 1}`;
}

/** 建点时的变量名前缀:输入按媒体类型,合成按产物类型,语音按模式,功能等选包后再定。 */
function varPrefixFor(kind: CanvasNodeKind, mediaKind?: MediaKind): string | null {
  if (kind === "input") return `input_${mediaKind ?? "text"}`;
  if (kind === "concat") return `output_${mediaKind === "audio" ? "audio" : "video"}`;
  if (kind === "speech") return "output_audio"; // 默认 tts;asr 由调用方改 mode 时一并改
  return null; // function: 选包后按 outputKind 分配
}

interface CanvasState {
  canvasId: string | null;
  name: string;
  nodes: CanvasFlowNode[];
  edges: Edge[];
  viewport: Viewport;
  dirty: boolean;
  /** 有节点处于 pending/running 时页面持续轮询 */
  runActive: boolean;
  /** 撤销/重做可用性（历史在模块级，非响应式） */
  canUndo: boolean;
  canRedo: boolean;

  load: (canvas: CanvasOut) => void;
  reset: () => void;
  setName: (name: string) => void;
  /** 保存成功打点:undo 回到该版本时不再误报未保存 */
  markSaved: () => void;
  serialize: () => CanvasGraph;

  onNodesChange: (changes: NodeChange<CanvasFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<Edge>[]) => void;
  onConnect: (conn: Connection) => ConnectRejectReason | null;
  setViewport: (vp: Viewport) => void;

  addNode: (
    kind: CanvasNodeKind,
    mediaKind: MediaKind | undefined,
    position: { x: number; y: number },
  ) => CanvasFlowNode;
  updateNodeData: (id: string, patch: Record<string, unknown>) => void;
  /** 用服务端 node_runs / 实时 plan 合并节点执行状态 */
  applyRuns: (
    runs: CanvasNodeRunOut[],
    plan?: { node_id: string; status: string; job_id: string | null; reused: boolean }[],
  ) => void;
  setRunActive: (active: boolean) => void;
  applyLayout: (positions: Map<string, { x: number; y: number }>) => void;

  undo: () => void;
  redo: () => void;
  /** 把多次变更合并为一步撤销（如选包自动补建输入节点） */
  batch: (fn: () => void) => void;
}

export type ConnectRejectReason = string;

/** 撤销历史：结构快照 {nodes, edges}，模块级存放（不需响应式）。 */
interface HistoryEntry {
  nodes: CanvasFlowNode[];
  edges: Edge[];
  /** 该快照所代表状态的版本号（dirty 基线比对用） */
  rev: number;
}
const HISTORY_LIMIT = 50;
let past: HistoryEntry[] = [];
let future: HistoryEntry[] = [];
/** 单调递增的版本号;markSaved 记下已保存版本,undo 回到该版本即不脏 */
let rev = 0;
let savedRev = 0;
/** 名称改动不在结构历史里,单独记脏,防止 rev 比对漏报 */
let nameDirty = false;
/** batch() 期间内部动作不再单独入栈 */
let batchDepth = 0;
/** 拖拽期间只记一次（首帧） */
let dragRecorded = false;
/** 面板编辑防抖合并:同一节点同一组键 800ms 内只入栈一次 */
let lastEditKey = "";
let lastEditAt = 0;
const EDIT_COALESCE_MS = 800;

function mergeRun(base: NodeRunState, patch: Partial<NodeRunState>): NodeRunState {
  return { ...base, ...patch, assetIds: patch.assetIds ?? base.assetIds };
}

export const useCanvasStore = create<CanvasState>()((set, get) => {
  const historySync = () => set({ canUndo: past.length > 0, canRedo: future.length > 0 });
  /** 变更前记录一步快照（batch 期间由 batch 自己记） */
  const record = () => {
    if (batchDepth > 0) return;
    past.push({ nodes: get().nodes, edges: get().edges, rev });
    if (past.length > HISTORY_LIMIT) past.shift();
    future = [];
    rev += 1;
    historySync();
  };

  /** 恢复快照,但 run 状态是服务端事实:保留每个节点当前的 run,并据此重算轮询开关。 */
  const restore = (entry: HistoryEntry) => {
    const currentRuns = new Map(get().nodes.map((n) => [n.id, n.data.run]));
    const nodes = entry.nodes.map((n) => {
      const run = currentRuns.get(n.id);
      if (run) return { ...n, data: { ...n.data, run } } as CanvasFlowNode;
      // 撤销复活的节点:本地早已删掉它,快照里的 running/pending 不可信
      // (服务端是否还在跑无法确认),回到 idle——下次执行时画布运行流会重建 run 记录
      const status = n.data.run.status;
      if (status === "running" || status === "pending") {
        return { ...n, data: { ...n.data, run: idleRun() } } as CanvasFlowNode;
      }
      return n;
    });
    set({
      nodes,
      edges: entry.edges,
      runActive: nodes.some((n) => ["pending", "running"].includes(n.data.run.status)),
    });
  };

  return {
    canvasId: null,
    name: "",
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    dirty: false,
    runActive: false,
    canUndo: false,
    canRedo: false,

  load: (canvas) => {
    const graph = canvas.graph;
    const runByNode = new Map(canvas.node_runs.map((r) => [r.node_id, r]));
    const nodes: CanvasFlowNode[] = (graph.nodes ?? []).map((n) => {
      const data = normalizeNodeData(n.type, n.data);
      const run = runByNode.get(n.id);
      if (run) {
        data.run = mergeRun(data.run, {
          status: run.status as NodeRunState["status"],
          jobId: run.job_id,
          assetIds: run.asset_ids,
          error: run.error,
          published: run.published,
        });
      }
      return { id: n.id, type: n.type, position: n.position, data };
    });
    const edges: Edge[] = (graph.edges ?? []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? undefined,
      targetHandle: e.targetHandle ?? undefined,
      type: "canvas",
    }));
    set({
      canvasId: canvas.id,
      name: canvas.name,
      nodes,
      edges,
      viewport: graph.viewport ?? { x: 0, y: 0, zoom: 1 },
      dirty: false,
      runActive: nodes.some((n) => ["pending", "running"].includes(n.data.run.status)),
    });
    // 换画布即另起历史与版本基线
    past = [];
    future = [];
    rev = 0;
    savedRev = 0;
    nameDirty = false;
    historySync();
  },

  reset: () => {
    past = [];
    future = [];
    rev = 0;
    savedRev = 0;
    nameDirty = false;
    set({
      canvasId: null,
      name: "",
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      dirty: false,
      runActive: false,
      canUndo: false,
      canRedo: false,
    });
  },

  setName: (name) => {
    // 名称随 graph 一起保存但不入结构历史;单独记脏,undo 的 rev 比对不会漏报它
    rev += 1;
    nameDirty = true;
    set({ name, dirty: true });
  },

  /** 保存成功打点:当前版本即干净基线 */
  markSaved: () => {
    savedRev = rev;
    nameDirty = false;
    set({ dirty: false });
  },

  serialize: () => {
    const { nodes, edges, viewport } = get();
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.type ?? "input") as CanvasGraph["nodes"][number]["type"],
        position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
        data: { ...n.data },
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
        targetHandle: e.targetHandle ?? null,
      })),
      viewport,
    };
  },

  onNodesChange: (changes) => {
    // 撤销记录:删/增节点一步一记;拖拽只在首帧记一次
    if (changes.some((c) => c.type === "remove" || c.type === "add")) record();
    if (changes.some((c) => c.type === "position" && c.dragging)) {
      if (!dragRecorded) {
        record();
        dragRecorded = true;
      }
    } else if (changes.some((c) => c.type === "position" && !c.dragging)) {
      dragRecorded = false;
    }
    const nodes = applyNodeChanges(changes, get().nodes);
    // 位置之外的变更（选择）不置脏；拖拽结束（dragging=false）才置脏
    const structural = changes.some(
      (c) => c.type === "remove" || c.type === "add" || (c.type === "position" && !c.dragging),
    );
    set({ nodes, dirty: get().dirty || structural });
  },

  onEdgesChange: (changes) => {
    const removed = changes.filter((c) => c.type === "remove").map((c) => c.id);
    if (removed.length) record();
    let nodes = get().nodes;
    if (removed.length) {
      // 断线后同步 concat 节点的 order
      const removedEdges = get().edges.filter((e) => removed.includes(e.id));
      const affectedTargets = new Set(removedEdges.map((e) => e.target));
      nodes = nodes.map((n) => {
        if (!affectedTargets.has(n.id) || n.data.kind !== "concat") return n;
        const removedSources = new Set(
          removedEdges.filter((e) => e.target === n.id).map((e) => e.source),
        );
        return {
          ...n,
          data: { ...n.data, order: n.data.order.filter((s) => !removedSources.has(s)) },
        };
      });
    }
    set({
      nodes,
      edges: applyEdgeChanges(changes, get().edges),
      dirty: get().dirty || changes.some((c) => c.type === "remove" || c.type === "add"),
    });
  },

  onConnect: (conn) => {
    const { nodes, edges } = get();
    const check = checkConnection(nodes, edges, conn);
    if (!check.ok) return check.reason;
    record();
    const edge: Edge = {
      id: `${conn.source}-${conn.target}-${Date.now().toString(36)}`,
      source: conn.source,
      target: conn.target,
      sourceHandle: conn.sourceHandle ?? undefined,
      targetHandle: conn.targetHandle ?? undefined,
      type: "canvas",
    };
    // concat 节点：新连入的源追加到 order 末尾
    const nodes2 = nodes.map((n) => {
      if (n.id !== conn.target || n.data.kind !== "concat") return n;
      if (n.data.order.includes(conn.source)) return n;
      return { ...n, data: { ...n.data, order: [...n.data.order, conn.source] } };
    });
    set({ nodes: nodes2, edges: [...edges, edge], dirty: true });
    return null;
  },

  setViewport: (viewport) => set({ viewport }),

  addNode: (kind, mediaKind, position) => {
    record();
    const data = createDefaultNodeData(kind, mediaKind);
    const prefix = varPrefixFor(kind, mediaKind);
    if (prefix) data.varName = nextVarName(get().nodes, prefix);
    const node: CanvasFlowNode = {
      id: newNodeId(kind),
      type: kind,
      position,
      data,
      selected: true,
    };
    set({
      nodes: [...get().nodes.map((n) => ({ ...n, selected: false })), node],
      dirty: true,
    });
    return node;
  },

  updateNodeData: (id, patch) => {
    // 面板编辑也入历史:同一节点同一组键 800ms 内合并(连续打字不刷屏),
    // 离散操作(换组/绑定/排序)各自成步。
    // 豁免:run 字段是服务端事实(发布标记等),不入历史——否则会产生视觉无操作的空 undo 步。
    const keys = Object.keys(patch);
    if (!(keys.length === 1 && keys[0] === "run") && batchDepth === 0) {
      const key = `${id}:${keys.sort().join(",")}`;
      const now = Date.now();
      if (key !== lastEditKey || now - lastEditAt > EDIT_COALESCE_MS) record();
      lastEditKey = key;
      lastEditAt = now;
    }
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? ({ ...n, data: { ...n.data, ...patch } } as CanvasFlowNode) : n,
      ),
      dirty: true,
    });
  },

  applyRuns: (runs, plan) => {
    const runByNode = new Map(runs.map((r) => [r.node_id, r]));
    const planByNode = new Map((plan ?? []).map((p) => [p.node_id, p]));
    const nodes = get().nodes.map((n) => {
      const persisted = runByNode.get(n.id);
      const live = planByNode.get(n.id);
      let run = n.data.run;
      if (persisted) {
        run = mergeRun(run, {
          status: persisted.status as NodeRunState["status"],
          jobId: persisted.job_id,
          assetIds: persisted.asset_ids,
          error: persisted.error,
          published: persisted.published,
        });
      }
      if (live) {
        run = mergeRun(run, {
          status: live.status as NodeRunState["status"],
          jobId: live.job_id ?? run.jobId,
          reused: live.reused,
        });
      }
      if (run === n.data.run) return n;
      return { ...n, data: { ...n.data, run } } as CanvasFlowNode;
    });
    set({
      nodes,
      runActive:
        (plan ?? []).some((p) => ["pending", "running"].includes(p.status)) ||
        nodes.some((n) => ["pending", "running"].includes(n.data.run.status)),
    });
  },

  setRunActive: (active) => set({ runActive: active }),

  applyLayout: (positions) => {
    record();
    set({
      nodes: get().nodes.map((n) => {
        const pos = positions.get(n.id);
        return pos ? { ...n, position: pos } : n;
      }),
      dirty: true,
    });
  },

  undo: () => {
    const prev = past.pop();
    if (!prev) return;
    future.push({ nodes: get().nodes, edges: get().edges, rev });
    dragRecorded = false;
    lastEditKey = "";
    rev = prev.rev;
    restore(prev);
    set({ dirty: rev !== savedRev || nameDirty });
    historySync();
  },

  redo: () => {
    const next = future.pop();
    if (!next) return;
    past.push({ nodes: get().nodes, edges: get().edges, rev });
    dragRecorded = false;
    lastEditKey = "";
    rev = next.rev;
    restore(next);
    set({ dirty: rev !== savedRev || nameDirty });
    historySync();
  },

  batch: (fn) => {
    // 嵌套 batch 只在最外层记录,避免一个复合动作产生多条历史
    const outermost = batchDepth === 0;
    if (outermost) {
      past.push({ nodes: get().nodes, edges: get().edges, rev });
      if (past.length > HISTORY_LIMIT) past.shift();
      future = [];
      rev += 1;
    }
    batchDepth++;
    try {
      fn();
    } finally {
      batchDepth--;
    }
    if (outermost) historySync();
  },
  };
});

export { idleRun };

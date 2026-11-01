/** 浏览器端画布工具：Agent 下发的改动直接在 zustand store 上执行。 */
import type { QueryClient } from "@tanstack/react-query";

import {
  api,
  type ExecutionSpec,
  type MediaSlot,
  type WorkflowInputSpec,
  type WorkflowPackOut,
} from "@/api/client";
import { applyMenuToNode, resolveSpec } from "@/canvas/applyMenu";
import { applyPackToNode } from "@/canvas/applyPack";
import { bindingSources, findNodeByVar } from "@/canvas/bindings";
import { layeredLayout } from "@/canvas/layout";
import { scopeOf, validateCanvas } from "@/canvas/preflight";
import type { CanvasNodeKind, MediaKind } from "@/canvas/types";
import { useCanvasUiStore } from "@/components/canvas/ui-state";
import { useCanvasStore } from "@/stores/canvas";

export interface ClientToolCall {
  id: string;
  name: string;
  arguments: string;
  args?: Record<string, unknown>;
  requires_confirm?: boolean;
  risk?: string;
  title?: string;
}

export interface ClientToolResult {
  tool_call_id: string;
  name: string;
  result: Record<string, unknown>;
}

export interface ClientToolContext {
  canvasId: string;
  queryClient: QueryClient;
  onFlash?: (text: string, opts?: { sticky?: boolean }) => void;
}

const KINDS = new Set<CanvasNodeKind>(["input", "function", "concat", "speech"]);
const MEDIA = new Set<MediaKind>(["image", "video", "audio", "text", "character"]);

/** 弱模型常用自然语言命名节点，落到画布真实类型上。 */
const KIND_ALIASES: Record<
  string,
  { kind: CanvasNodeKind; media?: MediaKind; data?: Record<string, unknown> }
> = {
  text_input: { kind: "input", media: "text" },
  input_text: { kind: "input", media: "text" },
  image_input: { kind: "input", media: "image" },
  input_image: { kind: "input", media: "image" },
  video_input: { kind: "input", media: "video" },
  input_video: { kind: "input", media: "video" },
  audio_input: { kind: "input", media: "audio" },
  input_audio: { kind: "input", media: "audio" },
  tts: { kind: "speech", media: "audio", data: { mode: "tts" } },
  text_to_speech: { kind: "speech", media: "audio", data: { mode: "tts" } },
  asr: { kind: "speech", media: "audio", data: { mode: "asr" } },
  speech_to_text: { kind: "speech", media: "audio", data: { mode: "asr" } },
};

function parseArgs(call: ClientToolCall): Record<string, unknown> {
  if (call.args && typeof call.args === "object") return call.args;
  try {
    const parsed = JSON.parse(call.arguments || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function defaultPosition() {
  const nodes = useCanvasStore.getState().nodes;
  if (!nodes.length) return { x: 0, y: 0 };
  return {
    x: Math.max(...nodes.map((node) => node.position.x)) + 320,
    y: Math.min(...nodes.map((node) => node.position.y)),
  };
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function bindingsOf(args: Record<string, unknown>): Record<string, string> {
  const raw = args.bindings ?? args.inputs;
  if (!isRecord(raw)) return {};
  return Object.fromEntries(
    Object.entries(raw)
      .map(([key, value]) => [String(key), String(value ?? "").trim()])
      .filter(([, value]) => value),
  );
}

interface BindingConnections {
  created: string[];
  missing: string[];
  rejected: { varName: string; reason: string }[];
}

/** 绑定只选槽：媒体变量必须有真实上游连线，缺边时补上。文本变量用 {{var}}，不建边。 */
function connectBindingSources(
  nodeId: string,
  bindings: Record<string, string>,
): BindingConnections {
  const result: BindingConnections = { created: [], missing: [], rejected: [] };
  for (const source of bindingSources(useCanvasStore.getState().nodes, bindings)) {
    const sourceNode = source.node;
    if (!sourceNode) {
      result.missing.push(source.varName);
      continue;
    }
    if (!source.mediaKind) continue;
    const store = useCanvasStore.getState();
    if (store.edges.some((edge) => edge.source === sourceNode.id && edge.target === nodeId)) {
      continue;
    }
    const outcome: { reason: string | null } = { reason: null };
    store.batch(() => {
      outcome.reason = useCanvasStore.getState().onConnect({
        source: sourceNode.id,
        target: nodeId,
        sourceHandle: `out-${sourceNode.id}`,
        targetHandle: `in-${nodeId}`,
      });
    });
    if (outcome.reason === null) result.created.push(source.varName);
    else if (outcome.reason !== "duplicate") {
      result.rejected.push({ varName: source.varName, reason: outcome.reason });
    }
  }
  return result;
}

function nodeIdOf(args: Record<string, unknown>): string {
  return String(args.node_id ?? args.nodeId ?? args.id ?? "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** 模型常把 patch 写成 data，或直接平铺字段；统一成待写入的节点 data。 */
function patchOf(args: Record<string, unknown>): Record<string, unknown> | null {
  const raw = args.patch ?? args.data;
  let patch: Record<string, unknown>;
  if (isRecord(raw)) {
    patch = raw;
  } else {
    patch = { ...args };
    delete patch.node_id;
    delete patch.nodeId;
  }
  if (!Object.keys(patch).length) return null;
  if (Object.keys(patch).length === 1 && isRecord(patch.data)) return patch.data;
  return patch;
}

async function loadPacks(queryClient: QueryClient): Promise<WorkflowPackOut[]> {
  return queryClient.ensureQueryData({
    queryKey: ["workflows"],
    queryFn: () => api.listWorkflows(),
  });
}

/** 套用功能菜单/工作流后允许覆盖的普通字段；执行目标字段由套装工具负责。 */
function extraDataPatch(args: Record<string, unknown>): Record<string, unknown> {
  const raw = isRecord(args.data) ? args.data : {};
  const blocked = new Set([
    "kind",
    "type",
    "media_kind",
    "mediaKind",
    "pack",
    "outputKind",
    "presetId",
    "presetTitle",
    "subCapability",
    "targetType",
    "targetId",
    "targetLabel",
    "providerId",
    "run",
  ]);
  return Object.fromEntries(Object.entries(raw).filter(([key]) => !blocked.has(key)));
}

function packMediaSlots(inputs: Record<string, WorkflowInputSpec>): MediaSlot[] {
  return Object.entries(inputs)
    .filter(([, spec]) => ["image", "video", "audio", "text"].includes(String(spec.type || "")))
    .map(([key, spec]) => ({
      key,
      type: String(spec.type || ""),
      label: String(spec.label || key),
      required: Boolean(spec.required),
      multiple: false,
    }));
}

function specForFunctionNode(
  data: Record<string, unknown>,
  specs: ExecutionSpec[],
  packs: WorkflowPackOut[],
  menu: Awaited<ReturnType<typeof api.getCanvasMenu>>,
): ExecutionSpec | undefined {
  const targetType = String(data.targetType || "");
  const targetId = String(data.targetId || data.pack || "");
  if (targetType === "model" || (targetType !== "workflow" && data.providerId != null)) {
    const hit = specs.find(
      (spec) =>
        spec.target_type === "model" &&
        spec.target_id === targetId &&
        (data.providerId == null || spec.provider_id === data.providerId),
    );
    if (hit) return hit;
  }
  if (targetType === "workflow" || data.pack) {
    const packName = String(data.pack || targetId);
    const hit = specs.find(
      (spec) => spec.target_type === "workflow" && spec.target_id === packName,
    );
    if (hit) return hit;
    const pack = packs.find((item) => item.name === packName);
    if (pack) {
      return {
        target_type: "workflow",
        target_id: pack.name,
        display_name: pack.name,
        sub_capability: String(data.subCapability || pack.capability),
        provider_type: "comfyui",
        provider_id: null,
        provider_name: "",
        category: "",
        media_slots: packMediaSlots(pack.inputs),
        inputs: pack.inputs,
      };
    }
  }
  const presetId = String(data.presetId || "");
  if (presetId) {
    const item = menu.find(
      (entry) => entry.id === presetId || entry.sub_capability === presetId,
    );
    if (item) return resolveSpec(item, specs);
  }
  return undefined;
}

const EDITABLE_FIELDS: Record<string, string[]> = {
  function: [
    "prompt",
    "varName",
    "values",
    "bindings",
    "accel",
    "audioMode",
    "bgmPath",
    "bgmVolume",
    "group",
  ],
  input: [
    "mediaKind",
    "assetId",
    "assetName",
    "maskAssetId",
    "text",
    "varName",
    "characterId",
    "characterSlot",
    "characterName",
    "characterDescription",
  ],
  concat: ["mediaKind", "order", "layout", "columns", "gap", "gapColor", "varName"],
  speech: [
    "mode",
    "text",
    "providerId",
    "voiceRecordId",
    "voice",
    "model",
    "workflow",
    "language",
    "format",
    "varName",
  ],
};

export async function executeClientTool(
  call: ClientToolCall,
  ctx: ClientToolContext,
): Promise<ClientToolResult> {
  const args = parseArgs(call);
  const store = useCanvasStore.getState();
  const ok = (result: Record<string, unknown>) => ({
    tool_call_id: call.id,
    name: call.name,
    result,
  });
  const fail = (error: string) => ok({ error });

  switch (call.name) {
    case "canvas_get_graph":
      return ok({ graph: store.serialize() });

    case "canvas_get_node": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node) return fail(`节点不存在: ${nodeId}`);
      return ok({
        node: { id: node.id, type: node.type, position: node.position, data: node.data },
      });
    }

    case "canvas_get_node_schema": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node) return fail(`节点不存在: ${nodeId}`);
      const data = node.data as Record<string, unknown>;
      const kind = String(data.kind || "");
      const [specs, packs, menu] = await Promise.all([
        ctx.queryClient.ensureQueryData({
          queryKey: ["execution-specs"],
          queryFn: () => api.executionSpecs(),
        }),
        loadPacks(ctx.queryClient),
        ctx.queryClient.ensureQueryData({
          queryKey: ["canvas-menu"],
          queryFn: () => api.getCanvasMenu(),
        }),
      ]);
      const spec = kind === "function" ? specForFunctionNode(data, specs, packs, menu) : undefined;
      return ok({
        node: { id: node.id, type: node.type, position: node.position, data: node.data },
        schema: {
          kind,
          editable_fields: EDITABLE_FIELDS[kind] ?? [],
          target: spec
            ? {
                target_type: spec.target_type,
                target_id: spec.target_id,
                display_name: spec.display_name,
                sub_capability: spec.sub_capability,
                provider_id: spec.provider_id,
                provider_name: spec.provider_name,
              }
            : null,
          media_slots: spec?.media_slots ?? [],
          inputs: spec?.inputs ?? {},
          values: kind === "function" ? (data.values ?? {}) : undefined,
          bindings: kind === "function" ? (data.bindings ?? {}) : undefined,
          notes: [
            "values 是整份替换：先读完整值，改目标键后再整份写回。",
            "本地视频包常用 length 帧数；云端模型常用 duration 秒。",
          ],
        },
      });
    }

    case "canvas_add_node": {
      // 兼容 {kind,...} 与 {node:{type,data,position}} 两种传参形态。
      const nodeSpec = isRecord(args.node) ? args.node : {};
      const specData = isRecord(nodeSpec.data) ? nodeSpec.data : {};
      const specKind =
        typeof specData.kind === "string" ? specData.kind : undefined;
      const rawKind = String(args.kind ?? specKind ?? nodeSpec.type ?? "input");
      const alias = KIND_ALIASES[rawKind];
      const kind = (alias?.kind ?? rawKind) as CanvasNodeKind;
      if (!KINDS.has(kind)) {
        return fail(
          `未知节点类型: ${rawKind}。可用 input/function/concat/speech；文字转语音用 speech + data.mode=tts。`,
        );
      }
      const rawMedia = String(
        args.media_kind ??
          args.mediaKind ??
          specData.media_kind ??
          specData.mediaKind ??
          alias?.media ??
          "",
      );
      const mediaKind = MEDIA.has(rawMedia as MediaKind)
        ? (rawMedia as MediaKind)
        : undefined;
      const specPosition = isRecord(nodeSpec.position) ? nodeSpec.position : {};
      const x = Number(args.x ?? specPosition.x);
      const y = Number(args.y ?? specPosition.y);
      const position =
        Number.isFinite(x) && Number.isFinite(y) ? { x, y } : defaultPosition();
      const specPatch = Object.fromEntries(
        Object.entries(specData).filter(
          ([key]) => !["kind", "type", "media_kind", "mediaKind", "run"].includes(key),
        ),
      );
      const rawData = {
        ...specPatch,
        ...(isRecord(args.data) ? args.data : {}),
      };
      const dataPatch = Object.fromEntries(
        Object.entries({ ...(alias?.data ?? {}), ...rawData }).filter(
          ([key]) => key !== "run",
        ),
      );
      if (
        kind === "function" &&
        (args.pack ||
          dataPatch.pack ||
          dataPatch.outputKind ||
          dataPatch.presetId ||
          dataPatch.menu)
      ) {
        return fail(
          "功能节点要先保持空白创建。创建后用 canvas_apply_menu（优先，menu_id 来自 list_canvas_menu）或 canvas_apply_pack（工作流包来自 list_workflows）绑定执行目标。",
        );
      }
      const requestedVar = String(dataPatch.varName ?? "");
      if (requestedVar) {
        const existing = store.nodes.find(
          (node) => (node.data as { varName?: string }).varName === requestedVar,
        );
        if (existing?.data.kind === kind) {
          return ok({
            node_id: existing.id,
            reused: true,
            note: `变量名 ${requestedVar} 已存在，复用节点`,
          });
        }
        if (existing) {
          return fail(
            `变量名 ${requestedVar} 已被节点 ${existing.id}（${existing.data.kind}）使用，请换一个 varName。`,
          );
        }
      }
      let nodeId = "";
      store.batch(() => {
        const node = useCanvasStore.getState().addNode(kind, mediaKind, position, {
          select: false,
        });
        nodeId = node.id;
        if (args.group) {
          useCanvasStore.getState().updateNodeData(node.id, { group: String(args.group) });
        }
        if (Object.keys(dataPatch).length) {
          useCanvasStore.getState().updateNodeData(node.id, dataPatch);
        }
      });
      return ok({ node_id: nodeId });
    }

    case "canvas_apply_menu": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node || node.data.kind !== "function") {
        return fail("只有功能节点可以套用功能菜单");
      }
      const wanted = String(args.menu_id ?? args.menuId ?? "");
      const menu = await ctx.queryClient.ensureQueryData({
        queryKey: ["canvas-menu"],
        queryFn: () => api.getCanvasMenu(),
      });
      const item =
        menu.find((entry) => entry.id === wanted) ??
        menu.find((entry) => entry.title === wanted) ??
        menu.find((entry) => entry.sub_capability === wanted);
      if (!item) {
        const names = menu
          .slice(0, 12)
          .map((entry) => `${entry.id}(${entry.title})`)
          .join("、");
        return fail(`功能菜单项不存在: ${wanted}。可用：${names}`);
      }
      const [specs, providers, packs] = await Promise.all([
        ctx.queryClient.ensureQueryData({
          queryKey: ["execution-specs"],
          queryFn: () => api.executionSpecs(),
        }),
        ctx.queryClient.ensureQueryData({
          queryKey: ["providers"],
          queryFn: api.listProviders,
        }),
        loadPacks(ctx.queryClient),
      ]);
      const spec = resolveSpec(item, specs);
      const extra = extraDataPatch(args);
      const bindings = bindingsOf(args);
      let created = 0;
      store.batch(() => {
        created = applyMenuToNode(node.id, item, spec, providers, packs, bindings);
        if (Object.keys(extra).length) {
          useCanvasStore.getState().updateNodeData(node.id, extra);
        }
      });
      const connections = connectBindingSources(node.id, bindings);
      return ok({
        node_id: node.id,
        menu_id: item.id,
        title: item.title,
        target_type: spec?.target_type ?? "",
        target_id: spec?.target_id ?? "",
        created_inputs: created,
        created_edges: connections.created,
        missing_bindings: connections.missing,
        rejected_edges: connections.rejected,
        note: spec ? "" : "当前没有已启用的工作流或模型，节点保持未绑定，先让用户选择目标。",
      });
    }

    case "canvas_apply_pack": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node || node.data.kind !== "function") {
        return fail("只有功能节点可以绑定工作流包");
      }
      const packName = String(args.pack ?? "");
      const packs = await loadPacks(ctx.queryClient);
      const pack = packs.find((item) => item.name === packName);
      if (!pack) {
        return fail(`工作流包不存在: ${packName}。先用 list_workflows 查可用包名。`);
      }
      const currentValues = (node.data as { values?: Record<string, string> }).values ?? {};
      const extra = extraDataPatch(args);
      const bindings = bindingsOf(args);
      let created = 0;
      store.batch(() => {
        created = applyPackToNode(node.id, pack, currentValues, bindings);
        if (Object.keys(extra).length) {
          useCanvasStore.getState().updateNodeData(node.id, extra);
        }
      });
      const connections = connectBindingSources(node.id, bindings);
      return ok({
        node_id: node.id,
        pack: pack.name,
        created_inputs: created,
        created_edges: connections.created,
        missing_bindings: connections.missing,
        rejected_edges: connections.rejected,
      });
    }

    case "canvas_update_node": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node) return fail(`节点不存在: ${nodeId}`);
      const patch = patchOf(args);
      if (!patch) return fail("patch 必须是对象");
      const { run: _run, ...safe } = patch;
      if (
        node.data.kind === "function" &&
        ("pack" in safe || "outputKind" in safe)
      ) {
        return fail(
          "功能节点的 pack/outputKind 由 canvas_apply_menu 或 canvas_apply_pack 设置，不要直接改。",
        );
      }
      store.batch(() => useCanvasStore.getState().updateNodeData(nodeId, safe));
      const connections = isRecord(safe.bindings)
        ? connectBindingSources(nodeId, bindingsOf({ bindings: safe.bindings }))
        : null;
      return ok({
        node_id: nodeId,
        updated: Object.keys(safe),
        ...(connections
          ? {
              created_edges: connections.created,
              missing_bindings: connections.missing,
              rejected_edges: connections.rejected,
            }
          : {}),
      });
    }

    case "canvas_connect": {
      const edgeSpec = isRecord(args.edge) ? args.edge : {};
      const source = String(
        args.source ??
          args.source_node_id ??
          args.sourceNodeId ??
          args.source_id ??
          args.sourceId ??
          args.source_node ??
          edgeSpec.sourceNodeId ??
          edgeSpec.source ??
          edgeSpec.source_id ??
          "",
      );
      const target = String(
        args.target ??
          args.target_node_id ??
          args.targetNodeId ??
          args.target_id ??
          args.targetId ??
          args.target_node ??
          edgeSpec.targetNodeId ??
          edgeSpec.target ??
          edgeSpec.target_id ??
          "",
      );
      let rejected: string | null = null;
      store.batch(() => {
        rejected = useCanvasStore.getState().onConnect({
          source,
          target,
          sourceHandle: `out-${source}`,
          targetHandle: `in-${target}`,
        });
      });
      if (rejected) return fail(`连线被拒绝: ${rejected}`);
      return ok({ edge: { source, target } });
    }

    case "canvas_disconnect": {
      const edgeSpec = isRecord(args.edge) ? args.edge : {};
      const edgeId = String(args.edge_id ?? args.edgeId ?? edgeSpec.id ?? "");
      const source = String(
        args.source ??
          args.source_node_id ??
          args.sourceNodeId ??
          args.source_id ??
          args.sourceId ??
          edgeSpec.sourceNodeId ??
          edgeSpec.source ??
          "",
      );
      const target = String(
        args.target ??
          args.target_node_id ??
          args.targetNodeId ??
          args.target_id ??
          args.targetId ??
          edgeSpec.targetNodeId ??
          edgeSpec.target ??
          "",
      );
      const edges = store.edges.filter(
        (edge) =>
          (edgeId && edge.id === edgeId) ||
          (!edgeId && edge.source === source && edge.target === target),
      );
      if (!edges.length) return fail("没有匹配的连线");
      store.batch(() =>
        useCanvasStore
          .getState()
          .onEdgesChange(edges.map((edge) => ({ type: "remove" as const, id: edge.id }))),
      );
      return ok({ removed: edges.map((edge) => edge.id) });
    }

    case "canvas_set_binding": {
      const nodeId = nodeIdOf(args);
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node || node.data.kind !== "function") return fail("只有功能节点能设置输入槽");
      const slot = String(args.slot ?? "");
      const source = String(args.source ?? "");
      if (!slot || !source) return fail("slot 和 source 不能为空");
      if (!findNodeByVar(store.nodes, source)) {
        return fail(`绑定变量 ${source} 不存在；先创建对应节点再连线`);
      }
      const previous = node.data.bindings ?? {};
      store.batch(() =>
        useCanvasStore.getState().updateNodeData(nodeId, {
          bindings: { ...previous, [slot]: source },
        }),
      );
      const connections = connectBindingSources(nodeId, { [slot]: source });
      if (connections.rejected.length) {
        const reason = connections.rejected[0].reason;
        store.batch(() =>
          useCanvasStore.getState().updateNodeData(nodeId, { bindings: previous }),
        );
        return fail(`绑定未生效：连线被拒绝（${reason}）`);
      }
      return ok({
        node_id: nodeId,
        slot,
        source,
        created_edges: connections.created,
        missing_bindings: connections.missing,
      });
    }

    case "canvas_layout": {
      const current = useCanvasStore.getState();
      useCanvasStore.getState().applyLayout(layeredLayout(current.nodes, current.edges));
      return ok({ arranged: current.nodes.length });
    }

    case "canvas_delete_nodes": {
      const ids = asList(args.node_ids ?? args.nodeIds ?? args.ids);
      if (!ids.length) return fail("node_ids 不能为空");
      store.batch(() => useCanvasStore.getState().deleteNodes(ids));
      return ok({ deleted: ids });
    }

    case "canvas_run_nodes": {
      const requested = asList(args.node_ids ?? args.nodeIds ?? args.ids);
      if (!requested.length) return fail("node_ids 不能为空");
      const force = Boolean(
        args.force ?? args.forced ?? args.force_run ?? args.forceRun,
      );
      const current = useCanvasStore.getState();
      // 模型偶尔会把上游一起传进来；只保留最下游的目标，避免重复提交上游。
      const ids = requested.filter(
        (id) =>
          !requested.some(
            (other) =>
              other !== id &&
              scopeOf(current.nodes, current.edges, [other]).has(id),
          ),
      );
      if (!ids.length) return fail("没有可执行的目标节点");
      const packs = await loadPacks(ctx.queryClient);
      const scope = scopeOf(current.nodes, current.edges, ids);
      const issues = validateCanvas(current.nodes, current.edges, packs, scope);
      if (issues.length) {
        useCanvasUiStore
          .getState()
          .setInvalidNodes(new Set(issues.map((issue) => issue.nodeId)));
        return fail(`预检未通过：${issues[0].message}`);
      }
      try {
        const saved = await api.updateCanvas(ctx.canvasId, {
          name: current.name.trim() || "未命名画布",
          graph: current.serialize(),
        });
        ctx.queryClient.setQueryData(["canvas", ctx.canvasId], saved);
        useCanvasStore.getState().markSaved();
        const result = await api.runCanvas(ctx.canvasId, {
          node_ids: ids,
          // 普通执行只强制当前节点，上游按指纹复用；强制才显式带上游。
          force_node_ids: force ? Array.from(scope) : ids,
        });
        useCanvasStore.getState().applyRuns(
          [],
          result.plan.map((item) => ({
            node_id: item.node_id,
            status: item.status,
            job_id: item.job_id,
            reused: item.reused,
          })),
        );
        useCanvasStore.getState().setRunActive(true);
        return ok({
          run_id: result.run_id,
          plan: result.plan.map((item) => ({
            node_id: item.node_id,
            status: item.status,
          })),
        });
      } catch (error) {
        return fail(error instanceof Error ? error.message : "执行失败");
      }
    }

    default:
      return fail(`未知画布工具: ${call.name}`);
  }
}

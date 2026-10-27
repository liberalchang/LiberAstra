/** 画布节点数据模型：可判别联合 + 默认值工厂 + 反序列化 normalize。
 *
 * 图结构即 React Flow 序列化格式（nodes/edges/viewport），直接落库。
 * 参考 open-canvas shared/lib/canvas/types.ts 的防御式 normalize 模式。
 */
import type { Edge, Node } from "@xyflow/react";

export type MediaKind = "image" | "video" | "audio" | "text";
export type CanvasNodeKind = "input" | "function" | "concat" | "speech";
export type ConcatMediaKind = "audio" | "video";
export type SpeechMode = "tts" | "asr";

export type NodeRunStatus =
  | "idle"
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled";

/** 节点最近一次执行状态（合并自服务端 node_runs / 实时 plan）。 */
export interface NodeRunState {
  status: NodeRunStatus;
  jobId?: string | null;
  assetIds: number[];
  error?: string | null;
  published?: boolean;
  reused?: boolean;
}

export interface InputNodeData extends Record<string, unknown> {
  kind: "input";
  mediaKind: MediaKind;
  /** 媒体输入引用的资产；文本输入为 null */
  assetId: number | null;
  assetName?: string;
  /** 蒙版资产(局部重绘用,仅图片输入;白区重绘黑区保留) */
  maskAssetId?: number | null;
  text?: string;
  /** 输出变量名(输入节点不做变换,变量即其资源引用);默认 input_{类型}_{n} */
  varName?: string;
  run: NodeRunState;
}

export interface FunctionNodeData extends Record<string, unknown> {
  kind: "function";
  /** 所属（工作流包分组名） */
  group: string;
  /** 选中的工作流包名 */
  pack: string;
  /** manifest 参数值（字符串化，提交时后端按类型转换） */
  values: Record<string, string>;
  /** Turbo LoRA 等加速配置（__accel 保留键） */
  accel?: { enabled: boolean; lora?: string; strength?: number } | null;
  /** 提示词原文；支持 {{varName}} 引用已连接文本输入 */
  prompt: string;
  /** 优化后提示词及其来源快照与启用开关（PromptField 三件套） */
  promptOptimized?: string;
  promptOptimizedFromRaw?: string;
  promptUseOptimized?: boolean;
  /** 所选包的产物媒体类型（选包时由 capability 推导，用于预览与连线校验） */
  outputKind?: MediaKind | null;
  /** 输出变量名;默认 output_{类型}_{n} */
  varName?: string;
  /** 输入槽绑定:包媒体参数名 → 上游节点输出变量名(未绑定的槽按类型顺序自动映射) */
  bindings?: Record<string, string>;
  run: NodeRunState;
}

export interface ConcatNodeData extends Record<string, unknown> {
  kind: "concat";
  mediaKind: ConcatMediaKind;
  /** 上游节点 id 的合成顺序（连线时自动同步，属性面板可手调） */
  order: string[];
  /** 输出变量名;默认 output_{类型}_{n} */
  varName?: string;
  run: NodeRunState;
}

export interface SpeechNodeData extends Record<string, unknown> {
  kind: "speech";
  /** tts=文字转语音(产音频);asr=语音转文字(吃音频,产文本/字幕) */
  mode: SpeechMode;
  /** tts 的文本内容,支持 {{varName}} */
  text?: string;
  /** 语音服务 Provider id;空 = 默认(第一个已启用且具该能力的服务) */
  providerId?: number | null;
  /** 音色库记录 id(Liber Speech 音色) */
  voiceRecordId?: number | null;
  /** edge-tts / OpenAI 兼容服务的音色名(如 zh-CN-XiaoxiaoNeural / alloy) */
  voice?: string;
  /** 服务模型名(OpenAI 系的 tts/stt 模型) */
  model?: string;
  /** Comfy 语音工作流包名(tts) */
  workflow?: string;
  /** asr 语言(空=自动) */
  language?: string;
  /** 输出变量名;tts → output_audio_n,asr → output_text_n */
  varName?: string;
  run: NodeRunState;
}

export type CanvasNodeData = InputNodeData | FunctionNodeData | ConcatNodeData | SpeechNodeData;
export type CanvasFlowNode = Node<CanvasNodeData, CanvasNodeKind>;

export const idleRun = (): NodeRunState => ({ status: "idle", assetIds: [] });

export function createDefaultNodeData(
  kind: CanvasNodeKind,
  mediaKind?: MediaKind,
): CanvasNodeData {
  if (kind === "input") {
    return {
      kind: "input",
      mediaKind: mediaKind ?? "image",
      assetId: null,
      text: "",
      varName: "",
      run: idleRun(),
    };
  }
  if (kind === "concat") {
    return {
      kind: "concat",
      mediaKind: mediaKind === "audio" ? "audio" : "video",
      order: [],
      run: idleRun(),
    };
  }
  if (kind === "speech") {
    return { kind: "speech", mode: "tts", text: "", voiceRecordId: null, language: "", run: idleRun() };
  }
  return { kind: "function", group: "", pack: "", values: {}, accel: null, prompt: "", run: idleRun() };
}

function normalizeRun(raw: unknown): NodeRunState {
  const r = (raw ?? {}) as Partial<NodeRunState>;
  return {
    status: (r.status as NodeRunStatus) ?? "idle",
    jobId: r.jobId ?? null,
    assetIds: Array.isArray(r.assetIds) ? r.assetIds.map(Number) : [],
    error: r.error ?? null,
    published: Boolean(r.published),
    reused: Boolean(r.reused),
  };
}

/** 从服务端/本地任意 JSON 恢复节点 data，缺字段回退默认。 */
export function normalizeNodeData(kind: CanvasNodeKind, raw: unknown): CanvasNodeData {
  const data = (raw ?? {}) as Record<string, unknown>;
  if (kind === "input") {
    return {
      kind: "input",
      mediaKind: (data.mediaKind as MediaKind) ?? "image",
      assetId: data.assetId == null ? null : Number(data.assetId),
      assetName: typeof data.assetName === "string" ? data.assetName : undefined,
      maskAssetId: data.maskAssetId == null ? null : Number(data.maskAssetId),
      text: typeof data.text === "string" ? data.text : "",
      varName: typeof data.varName === "string" ? data.varName : "",
      run: normalizeRun(data.run),
    };
  }
  if (kind === "concat") {
    return {
      kind: "concat",
      mediaKind: data.mediaKind === "audio" ? "audio" : "video",
      order: Array.isArray(data.order) ? data.order.map(String) : [],
      varName: typeof data.varName === "string" ? data.varName : "",
      run: normalizeRun(data.run),
    };
  }
  if (kind === "speech") {
    return {
      kind: "speech",
      mode: data.mode === "asr" ? "asr" : "tts",
      text: typeof data.text === "string" ? data.text : "",
      providerId: data.providerId == null ? null : Number(data.providerId),
      voiceRecordId: data.voiceRecordId == null ? null : Number(data.voiceRecordId),
      voice: typeof data.voice === "string" ? data.voice : "",
      model: typeof data.model === "string" ? data.model : "",
      workflow: typeof data.workflow === "string" ? data.workflow : "",
      language: typeof data.language === "string" ? data.language : "",
      varName: typeof data.varName === "string" ? data.varName : "",
      run: normalizeRun(data.run),
    };
  }
  return {
    kind: "function",
    group: typeof data.group === "string" ? data.group : "",
    pack: typeof data.pack === "string" ? data.pack : "",
    values:
      data.values && typeof data.values === "object"
        ? Object.fromEntries(
            Object.entries(data.values as Record<string, unknown>).map(([k, v]) => [k, String(v)]),
          )
        : {},
    accel: (data.accel as FunctionNodeData["accel"]) ?? null,
    prompt: typeof data.prompt === "string" ? data.prompt : "",
    promptOptimized: typeof data.promptOptimized === "string" ? data.promptOptimized : "",
    promptOptimizedFromRaw:
      typeof data.promptOptimizedFromRaw === "string" ? data.promptOptimizedFromRaw : "",
    promptUseOptimized: Boolean(data.promptUseOptimized),
    outputKind: (data.outputKind as MediaKind | null) ?? null,
    varName: typeof data.varName === "string" ? data.varName : "",
    bindings:
      data.bindings && typeof data.bindings === "object"
        ? Object.fromEntries(
            Object.entries(data.bindings as Record<string, unknown>).map(([k, v]) => [k, String(v)]),
          )
        : {},
    run: normalizeRun(data.run),
  };
}

/** 功能节点的产物类型由包 capability 决定（执行前用于连线兼容判断）。 */
export function outputKindOfCapability(capability: string | undefined): MediaKind | null {
  if (!capability) return null;
  if (["t2i", "i2i", "upscale"].includes(capability)) return "image";
  if (["t2v", "i2v", "avatar", "motion"].includes(capability)) return "video";
  return null;
}

/** 节点的产物媒体类型（连边校验用）；null = 不产生媒体（文本输入）。 */
export function nodeOutputKind(
  node: CanvasFlowNode,
  capabilityOf?: (pack: string) => string | undefined,
): MediaKind | null {
  const data = node.data;
  if (data.kind === "input") return data.mediaKind === "text" ? null : data.mediaKind;
  if (data.kind === "concat") return data.mediaKind;
  if (data.kind === "speech") return data.mode === "tts" ? "audio" : null;
  // 功能节点:选包时写入的 outputKind 是权威;查表只是兜底。
  // 此前只走 capabilityOf,不传回调的调用方(槽位绑定/连线校验)会把功能节点产物误判为 null。
  return data.outputKind ?? outputKindOfCapability(capabilityOf?.(data.pack));
}

export type CanvasEdge = Edge;

/** 画布节点数据模型：可判别联合 + 默认值工厂 + 反序列化 normalize。
 *
 * 图结构即 React Flow 序列化格式（nodes/edges/viewport），直接落库。
 * 参考 open-canvas shared/lib/canvas/types.ts 的防御式 normalize 模式。
 */
import type { Edge, Node } from "@xyflow/react";

export type MediaKind = "image" | "video" | "audio" | "text" | "character";
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

/** 输入节点的版本:原始/涂抹/裁剪各为一版;蒙版挂在所属版本上(像素对齐,不独立流通)。 */
export interface InputVersion {
  assetId: number;
  /** 版本标签:原始 / 涂抹 N / 裁剪 N / 深度 N */
  label: string;
  maskAssetId?: number | null;
  /** 产生该版本的操作 */
  op?: "markup" | "crop" | "depth";
}

export interface InputNodeData extends Record<string, unknown> {
  kind: "input";
  mediaKind: MediaKind;
  /** 媒体输入引用的资产；文本输入为 null。= 当前版本的 assetId(镜像) */
  assetId: number | null;
  assetName?: string;
  /** 蒙版资产(局部重绘用,仅图片输入;白区重绘黑区保留)。= 当前版本的蒙版(镜像) */
  maskAssetId?: number | null;
  /** 版本历史(仅图片输入):首项为原始图;涂抹/裁剪产生新版本 */
  versions?: InputVersion[];
  text?: string;
  /** 输出变量名(输入节点不做变换,变量即其资源引用);默认 input_{类型}_{n} */
  varName?: string;
  /** 角色输入：一个人，入镜视角在下游按槽位数展开 */
  characterId?: number | null;
  characterSlot?: string;
  characterName?: string;
  characterDescription?: string;
  run: NodeRunState;
}

export interface FunctionNodeData extends Record<string, unknown> {
  kind: "function";
  /** 所属（工作流包分组名） */
  group: string;
  /** 选中的工作流包名。云端模型节点为空。 */
  pack: string;
  /** 画布菜单项。有它时卡片用简称，属性面板按该能力过滤。 */
  presetId?: string;
  presetTitle?: string;
  subCapability?: string;
  targetType?: string;
  targetId?: string;
  targetLabel?: string;
  providerId?: number | null;
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
  /** 动作迁移声音来源。数字人固定为模型音轨。 */
  audioMode?: "model" | "reference";
  /** 音乐库相对路径，如 bgm/name.mp3。空表示不混背景音乐。 */
  bgmPath?: string;
  bgmVolume?: number;
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
  /** 来源菜单项。有它时属性里的服务商和模型按该菜单的匹配方式过滤。 */
  presetId?: string;
  presetTitle?: string;
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
  /** asr 语言(空=自动)；Liber Speech 的朗读语言也写在这里 */
  language?: string;
  /** tts: mp3 / wav / ogg_opus。asr: txt / json / srt / vtt，空为自动。 */
  format?: string;
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
      characterId: null,
      characterSlot: mediaKind === "character" ? "front" : undefined,
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
    const assetId = data.assetId == null ? null : Number(data.assetId);
    const maskAssetId = data.maskAssetId == null ? null : Number(data.maskAssetId);
    const versions = Array.isArray(data.versions)
      ? (data.versions as Record<string, unknown>[])
          .filter((v) => v && v.assetId != null)
          .map((v) => ({
            assetId: Number(v.assetId),
            label: typeof v.label === "string" ? v.label : "版本",
            maskAssetId: v.maskAssetId == null ? null : Number(v.maskAssetId),
          }))
      : // 旧画布没有版本列表:由当前资产合成(原始一版,蒙版挂当前)
        assetId != null
        ? [{ assetId, label: "原始", maskAssetId }]
        : [];
    return {
      kind: "input",
      mediaKind: (data.mediaKind as MediaKind) ?? "image",
      assetId,
      assetName: typeof data.assetName === "string" ? data.assetName : undefined,
      maskAssetId,
      versions,
      text: typeof data.text === "string" ? data.text : "",
      varName: typeof data.varName === "string" ? data.varName : "",
      characterId: data.characterId == null ? null : Number(data.characterId),
      characterSlot:
        typeof data.characterSlot === "string"
          ? data.characterSlot
          : data.mediaKind === "character"
            ? "front"
            : undefined,
      characterName: typeof data.characterName === "string" ? data.characterName : undefined,
      characterDescription:
        typeof data.characterDescription === "string" ? data.characterDescription : "",
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
      presetId: typeof data.presetId === "string" ? data.presetId : "",
      presetTitle: typeof data.presetTitle === "string" ? data.presetTitle : "",
      mode: data.mode === "asr" ? "asr" : "tts",
      text: typeof data.text === "string" ? data.text : "",
      providerId: data.providerId == null ? null : Number(data.providerId),
      voiceRecordId: data.voiceRecordId == null ? null : Number(data.voiceRecordId),
      voice: typeof data.voice === "string" ? data.voice : "",
      model: typeof data.model === "string" ? data.model : "",
      workflow: typeof data.workflow === "string" ? data.workflow : "",
      language: typeof data.language === "string" ? data.language : "",
      format: typeof data.format === "string" ? data.format : "",
      varName: typeof data.varName === "string" ? data.varName : "",
      run: normalizeRun(data.run),
    };
  }
  return {
    kind: "function",
    group: typeof data.group === "string" ? data.group : "",
    pack: typeof data.pack === "string" ? data.pack : "",
    presetId: typeof data.presetId === "string" ? data.presetId : "",
    presetTitle: typeof data.presetTitle === "string" ? data.presetTitle : "",
    subCapability: typeof data.subCapability === "string" ? data.subCapability : "",
    targetType: typeof data.targetType === "string" ? data.targetType : "",
    targetId: typeof data.targetId === "string" ? data.targetId : "",
    targetLabel: typeof data.targetLabel === "string" ? data.targetLabel : "",
    providerId: data.providerId == null || data.providerId === "" ? null : Number(data.providerId),
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
    audioMode: data.audioMode === "reference" ? "reference" : "model",
    bgmPath: typeof data.bgmPath === "string" ? data.bgmPath : "",
    bgmVolume: Number.isFinite(Number(data.bgmVolume)) ? Number(data.bgmVolume) : 0.2,
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
  if (["t2i", "i2i", "i2i_single", "i2i_multi", "inpaint", "color_grade", "outfit_swap", "depth_pose", "depth_gen", "upscale"].includes(capability)) return "image";
  if (["t2v", "i2v", "i2v_first", "i2v_flf", "i2v_orbit", "i2v_enhance", "t2v_enhance", "v2v_ref", "avatar", "motion"].includes(capability)) return "video";
  if (["analysis", "video_analysis", "asr"].includes(capability)) return "text";
  if (capability === "tts") return "audio";
  return null;
}

/** 节点的产物媒体类型（连边校验用）；null = 不产生媒体（文本输入）。 */
export function nodeOutputKind(
  node: CanvasFlowNode,
  capabilityOf?: (pack: string) => string | undefined,
): MediaKind | null {
  const data = node.data;
  if (data.kind === "input") {
    if (data.mediaKind === "text") return null;
    // 角色节点产出的是图片，下游按图片槽接收。
    if (data.mediaKind === "character") return "image";
    return data.mediaKind;
  }
  if (data.kind === "concat") return data.mediaKind;
  if (data.kind === "speech") return data.mode === "tts" ? "audio" : null;
  // 功能节点:选包时写入的 outputKind 是权威;查表只是兜底。
  // 此前只走 capabilityOf,不传回调的调用方(槽位绑定/连线校验)会把功能节点产物误判为 null。
  return data.outputKind ?? outputKindOfCapability(capabilityOf?.(data.pack));
}

export type CanvasEdge = Edge;

import { finishUpload, startUpload, updateUpload } from "@/lib/uploadProgress";
import type { components } from "./types";

/** 与后端 LIBERASTRA_COMFY_MAX_UPLOAD_MB 默认值一致（ComfyUI 默认 100MB）。超限时不发请求。 */
const MAX_UPLOAD_MB = 100;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

function assertUploadSize(file: File) {
  if (file.size <= MAX_UPLOAD_BYTES) return;
  const mb = (file.size / (1024 * 1024)).toFixed(1);
  throw new ApiError(400, `${file.name} 超过上传上限 ${MAX_UPLOAD_MB}MB（当前 ${mb}MB），已拒绝上传`);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

/** 401 时的全局回调（由 auth store 注册为登出）。仅当前持有 token 时才触发。 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function requestForm<T>(path: string, form: FormData, method = "POST"): Promise<T> {
  const files = Array.from(form.values()).filter((value): value is File => value instanceof File);
  const label = files.length === 1 ? files[0].name : files.length > 1 ? `${files.length} 个文件` : "";
  const taskId = label ? startUpload(label) : null;
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      if (taskId != null) finishUpload(taskId);
    };
    xhr.open(method, path);
    if (authToken) xhr.setRequestHeader("Authorization", `Bearer ${authToken}`);
    xhr.upload.onprogress = (event) => {
      if (taskId != null && event.lengthComputable && event.total > 0) {
        updateUpload(taskId, (event.loaded / event.total) * 100);
      }
    };
    xhr.onload = () => {
      done();
      if (xhr.status === 401 && authToken && onUnauthorized) onUnauthorized();
      if (xhr.status === 204) {
        resolve(undefined as T);
        return;
      }
      let payload: unknown = null;
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        reject(new ApiError(xhr.status, "响应解析失败"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as T);
        return;
      }
      const detail =
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : xhr.statusText;
      reject(new ApiError(xhr.status, detail));
    };
    xhr.onerror = () => {
      done();
      reject(new ApiError(0, "网络错误，上传失败"));
    };
    xhr.onabort = () => {
      done();
      reject(new ApiError(0, "上传已取消"));
    };
    xhr.send(form);
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (init?.body instanceof FormData) {
    return requestForm<T>(path, init.body, init.method ?? "POST");
  }
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401 && authToken && onUnauthorized) {
    // 登录态过期：清掉 token，Layout 会把页面导航回登录页
    onUnauthorized();
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* 非 JSON 响应 */
    }
    throw new ApiError(resp.status, String(detail));
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(path, { headers });
  if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
  return resp.blob();
}

export type AuthStatus = components["schemas"]["AuthStatus"];
export type UserOut = components["schemas"]["UserOut"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type ProviderTypeInfo = components["schemas"]["ProviderTypeInfo"];
export type CapabilitiesOut = components["schemas"]["CapabilitiesOut"];
export type ProviderOut = components["schemas"]["ProviderOut"];

/** 服务商模型目录里的一条。存在 Provider.extra.model_catalog。 */
export interface ModelItem {
  id: string;
  label: string;
  category: "llm" | "image" | "video" | "tts" | "asr" | string;
  sub_capabilities: string[];
  enabled: boolean;
  custom: boolean;
  /** 对话的最大输出，或火山图像 / 视频的表单默认值。未知模型不带这项。 */
  params?: {
    max_output?: number;
    defaults?: Record<string, string | number | boolean>;
  };
}

export interface MediaSlot {
  key: string;
  type: string;
  label: string;
  required: boolean;
  multiple: boolean;
  /** 画布补建的节点种类。动作迁移的人物图是 character。 */
  input_kind?: string;
}

/** 工作流包与云端模型共用的执行契约。 */
export interface ExecutionSpec {
  target_type: "workflow" | "model" | string;
  target_id: string;
  display_name: string;
  sub_capability: string;
  provider_type: string;
  provider_id: number | null;
  provider_name: string;
  category: string;
  media_slots: MediaSlot[];
  inputs: Record<string, WorkflowInputSpec>;
}

export interface CanvasMenuTarget {
  provider_id: number | null;
  target_type: "model" | "workflow" | "tool" | string;
  target_id: string;
}

export interface CanvasMenuItem {
  id: string;
  category: "speech" | "image" | "video" | "tool" | string;
  title: string;
  hint: string;
  sub_capability: string;
  bind_mode: "auto" | "manual" | "fixed" | string;
  manual_targets: CanvasMenuTarget[];
  default_target: CanvasMenuTarget | null;
  /** 关闭后不出现在画布功能菜单里。缺省视为开启。 */
  enabled?: boolean;
  /** 该能力的默认前置槽。还没绑定具体工作流或模型时，用它补输入节点。 */
  media_slots?: MediaSlot[];
}
export type TestResult = components["schemas"]["TestResult"];

export interface ProviderCreateInput {
  name: string;
  type: string;
  base_url?: string;
  api_key?: string;
  concurrency?: number;
  enabled?: boolean;
}

export interface JobOutput {
  type: string;
  content?: string;
  asset_id?: number;
  kind?: string;
  format?: string;
  filename?: string;
  /** prompt.optimize 等任务附带的元信息 */
  provider_name?: string;
  model?: string;
}

export interface JobOut {
  id: string;
  kind: string;
  function?: string | null;
  status: "pending" | "running" | "succeeded" | "failed" | "canceled";
  progress: number;
  provider_id?: number | null;
  model?: string | null;
  params?: Record<string, unknown>;
  outputs: JobOutput[];
  steps: { name: string; at: string }[];
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface VoiceOut {
  id: number;
  name: string;
  provider_id: number | null;
  voice_id: string | null;
  ref_audio_path: string | null;
  ref_text: string | null;
  tags: string[];
  is_default: boolean;
  created_at: string;
}

export interface CharacterOut {
  id: number;
  name: string;
  description: string;
  portrait_path: string | null;
  turnaround_path: string | null;
  front_path: string | null;
  side_path: string | null;
  back_path: string | null;
  voice_record_id: number | null;
  voice_name: string | null;
  tags: string[];
  created_at: string;
}

export interface AssetOut {
  id: number;
  kind: string;
  path: string;
  mime: string | null;
  size: number;
  job_id: string | null;
  meta: Record<string, unknown>;
  hidden: boolean;
  created_at: string;
}

export interface AssetJobOut {
  job_id: string;
  job_kind: string;
  created_at: string;
  asset_count: number;
  kinds: string[];
}

export interface PluginOut {
  id: string;
  name: string;
  description: string;
  port: number;
  installed: boolean;
  enabled: boolean;
  running: boolean;
  device: string;
  models_dir: string;
  code_dir: string;
  launch: string;
  model_status: string;
  env_status: string;
  env_dir: string;
  install_progress: number;
  install_phase: string;
  last_error: string;
}

export interface SystemPreferences {
  /** ComfyUI 出图/出视频等待上限（秒） */
  comfy_wait_timeout_seconds: number;
  /** 同步接口（wait=true）等待任务终态的上限（秒） */
  api_wait_timeout_seconds: number;
  /** LLM（Ollama / OpenAI 兼容）单次 chat 读超时（秒） */
  llm_request_timeout_seconds: number;
  /** 同主机服务串行执行：0=并行（默认），1=同一主机上的 Provider 任务互斥 */
  serial_same_host: number;
  /** 默认 LLM Provider id；0=自动取第一个启用的 llm */
  default_llm_provider_id: number;
  /** 默认 LLM 模型名；空则用 Provider.extra.model 或已拉取列表首项 */
  default_llm_model: string;
  /** 深度图 Provider id；0=自动取第一个启用的 depth */
  default_depth_provider_id: number;
  /** 深度图模型名；空则由深度服务使用 dpt_swin2_large_384 */
  default_depth_model: string;
  /** 角色定妆照图像 Provider id；0=自动取第一个启用的 image */
  default_character_provider_id: number;
  /** 角色四段式定妆照使用的文生图工作流包 */
  default_character_workflow: string;
  /** 一张参考图时使用的图生图工作流包 */
  default_character_i2i_workflow: string;
  /** 两到三张参考图时使用的多图编辑工作流包 */
  default_character_i2i_multi_workflow: string;
  /** Liber Speech 默认文字转语音模型包 */
  default_speech_model: string;
  /** Liber Speech 默认语音转文字模型；空表示跟随语音服务 .env */
  default_asr_model: string;
  /** 默认换音模型；空表示跟随语音服务 .env */
  default_vc_model: string;
}

/** 语音服务 GET /api/v1/models 里的一项可选模型。 */
export interface SpeechCatalogModel {
  id: string;
  label: string;
  group?: string;
  languages?: string[];
}

/** 系统设置两个下拉框的数据来源。 */
export interface SpeechModelCatalog {
  tts_models: SpeechCatalogModel[];
  asr_models: SpeechCatalogModel[];
  vc_models: SpeechCatalogModel[];
  default_tts_model: string;
  default_asr_model: string;
  default_vc_model: string;
  separate_available: boolean;
}

export type PromptOrigin = "builtin" | "customized" | "user";

export interface PromptTaskOut {
  id: string;
  name: string;
  capabilities: string[];
  system: string;
  /** 是否有用户覆盖(true=已自定义或用户自建) */
  custom?: boolean;
  origin?: PromptOrigin;
}

export interface PromptSceneOut {
  id: string;
  name: string;
  append: string;
  custom?: boolean;
  origin?: PromptOrigin;
}

export interface PromptOptimizeInput {
  prompt: string;
  task?: string;
  scene?: string;
  workflow?: string;
  aspect?: string;
  extra_context?: string;
  provider_id?: number;
  model?: string;
}


export interface WorkflowInputSpec {
  node: string;
  field: string;
  type: string;
  default?: unknown;
  min?: number;
  max?: number;
  required?: boolean;
  description?: string;
  /** 中文显示名，缺省时用内置映射或参数名 */
  label?: string;
  /** 提示词里这个槽位要写成的称呼。画布 / 插入 label，提交时换成 mention */
  mention?: string;
  /** 从 ComfyUI 的某个模型目录拉取选项（如 checkpoints、upscale_models），渲染为下拉框 */
  options_from?: string;
  /** 静态下拉选项（本机 TTS 音色等，不依赖 ComfyUI） */
  options?: string[];
  /** 帧数对齐：有效帧数 = align_base × k + align_offset（如 MiniMax 的 17k+5） */
  align_base?: number;
  align_offset?: number;
  /** 宽高的取值倍数（视频潜变量压缩比，MiniMax 系为 32，Wan 系为 16） */
  multiple?: number;
}

/** 工作流包 accel（Turbo / Uncensored LoRA 等）；空对象表示无该能力 */
export interface WorkflowAccelSpec {
  label?: string;
  /** 开启时说明；缺省按 Turbo 文案 */
  hint?: string;
  /** 关闭时说明 */
  hint_off?: string;
  lora_label?: string;
  strength_label?: string;
  family?: string;
  default_enabled?: boolean;
  node?: string;
  bypass_input?: string;
  lora?: {
    field?: string;
    options_from?: string;
    match?: string;
    recommended?: string;
  };
  strength?: {
    field?: string;
    default?: number;
    min?: number;
    max?: number;
  };
  preset?: Record<string, unknown>;
}

export interface WorkflowPackOut {
  name: string;
  capability: string;
  description: string;
  inputs: Record<string, WorkflowInputSpec>;
  outputs: Record<string, unknown>;
  source: string;
  requirements: Record<string, unknown>;
  /** 视频包帧率；有它参数表单的"帧数"可按秒设置 */
  fps?: number | null;
  /** 加速 LoRA 声明；空=无加速能力（前端有值时再渲染开关） */
  accel?: WorkflowAccelSpec;
}

export interface TemplateOut {
  name: string;
  aspect: string;
  type: "static" | "image" | "video" | "asset";
  type_label: string;
  source: "builtin" | "user";
  width: number;
  height: number;
  media_width: number;
  media_height: number;
  /** 模板是否含 {{image}} 占位符（决定插图模式是否逐镜出图） */
  needs_image: boolean;
  params: Record<string, { type: string; default: unknown }>;
}

export interface BgmOut {
  name: string;
  size: number;
}

/** 导出的完整工作流包（含 workflow JSON），可用于编辑与再导入。 */
export interface WorkflowPackBundle extends WorkflowPackOut {
  workflow: Record<string, unknown>;
  /** 优化器技术说明(后端 export 时透传,空=未设置) */
  llm_note?: string;
}

/** 画布节点最近一次执行记录（服务端持久化）。 */
export interface CanvasNodeRunOut {
  node_id: string;
  status: string;
  job_id: string | null;
  asset_ids: number[];
  error: string | null;
  published: boolean;
}

/** React Flow 可序列化的画布图（data 开放,由前端节点类型解释）。 */
export interface CanvasGraph {
  nodes: {
    id: string;
    type: "input" | "function" | "concat" | "speech";
    position: { x: number; y: number };
    data: Record<string, unknown>;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
  }[];
  viewport: { x: number; y: number; zoom: number };
}

export interface CanvasOut {
  id: string;
  name: string;
  graph: CanvasGraph;
  created_at: string;
  updated_at: string;
  node_runs: CanvasNodeRunOut[];
}

export interface CanvasListOut {
  id: string;
  name: string;
  node_count: number;
  created_at: string;
  updated_at: string;
}

export interface CanvasRunPlanItem {
  node_id: string;
  job_id: string | null;
  status: string;
  reused: boolean;
}

export interface CanvasRunOut {
  run_id: string;
  plan: CanvasRunPlanItem[];
}

export interface CanvasRunCancelOut {
  run_id: string | null;
  canceled_jobs: string[];
}

/** 工作流包分组（所属）:组名 → 包名列表 */
export type CanvasGroups = Record<string, string[]>;

export const TERMINAL_STATUSES = ["succeeded", "failed", "canceled"];

// ---- 导演台 ----

export interface AgentSessionOut {
  id: string;
  canvas_id: string | null;
  title: string;
  provider_id: number | null;
  model: string | null;
  active_skill: string;
  skill_state: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentMessageOut {
  id: number;
  role: "user" | "assistant" | "tool" | "event" | string;
  content: Record<string, unknown>;
  created_at: string;
}

export interface AgentSkillFileOut {
  path: string;
  size: number;
  is_text: boolean;
}

export interface AgentSkillOut {
  name: string;
  description: string;
  source: "builtin" | "user" | string;
  builtin: boolean;
  enabled: boolean;
  version: number;
  license?: string;
  compatibility?: string;
  allowed_tools?: string[];
  file_count?: number;
  has_scripts?: boolean;
}

export interface AgentAttachment {
  asset_id: number;
  kind: string;
  name?: string;
  /** false = 仅用于画布节点，不发给模型；默认 true。 */
  send_to_model?: boolean;
}

export interface AgentRefAsset {
  asset_id: number;
  kind: string;
}

/** 浏览器解析 @变量 后提交给后端的节点引用。 */
export interface AgentRef {
  node_id: string;
  var_name?: string;
  title?: string;
  kind?: string;
  config?: Record<string, unknown>;
  assets?: AgentRefAsset[];
  asset_ids?: number[];
  text?: string;
}

export interface AgentTurnInput {
  text: string;
  attachments: AgentAttachment[];
  refs: AgentRef[];
  provider_id?: number | null;
  model?: string;
  active_skill?: string | null;
}

export interface AgentSseEvent {
  event: string;
  data: Record<string, unknown>;
}

/** 浏览器端解析 SSE；原生 EventSource 带不上 Authorization 头。 */
export async function streamAgentEvents(
  path: string,
  body: unknown,
  onEvent: (event: AgentSseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (resp.status === 401 && authToken && onUnauthorized) onUnauthorized();
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const payload = await resp.json();
      detail = payload.detail ?? detail;
    } catch {
      /* 非 JSON 响应 */
    }
    throw new ApiError(resp.status, String(detail));
  }
  if (!resp.body) return;
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const raw = data.join("\n");
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      parsed = { text: raw };
    }
    onEvent({ event, data: parsed });
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      if (block.trim()) flush(block);
      index = buffer.indexOf("\n\n");
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) flush(buffer);
}

export const api = {
  authStatus: () => request<AuthStatus>("/api/v1/auth/status"),
  setup: (username: string, password: string) =>
    request<UserOut>("/api/v1/auth/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<UserOut>("/api/v1/auth/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>("/api/v1/auth/password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  getPreferences: () => request<SystemPreferences>("/api/v1/system/preferences"),
  getSpeechCatalog: () => request<SpeechModelCatalog>("/api/v1/system/speech-models"),
  updatePreferences: (body: Partial<SystemPreferences>) =>
    request<SystemPreferences>("/api/v1/system/preferences", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  healthz: () => request<{ status: string; version: string }>("/healthz"),

  capabilities: () => request<CapabilitiesOut>("/api/v1/capabilities"),
  listProviders: () => request<ProviderOut[]>("/api/v1/providers"),
  createProvider: (body: ProviderCreateInput) =>
    request<ProviderOut>("/api/v1/providers", { method: "POST", body: JSON.stringify(body) }),
  updateProvider: (id: number, body: Partial<ProviderCreateInput>) =>
    request<ProviderOut>(`/api/v1/providers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteProvider: (id: number) =>
    request<void>(`/api/v1/providers/${id}`, { method: "DELETE" }),
  testProvider: (id: number) =>
    request<TestResult>(`/api/v1/providers/${id}/test`, { method: "POST" }),
  fetchProviderModels: (id: number) => request<string[]>(`/api/v1/providers/${id}/models`),
  saveProviderCatalog: (id: number, models: ModelItem[]) =>
    request<ProviderOut>(`/api/v1/providers/${id}/catalog`, {
      method: "PUT",
      body: JSON.stringify({ models }),
    }),
  executionSpecs: (subCapability?: string) =>
    request<ExecutionSpec[]>(
      `/api/v1/providers/execution-specs${subCapability ? `?sub_capability=${encodeURIComponent(subCapability)}` : ""}`,
    ),
  getCanvasMenu: () => request<CanvasMenuItem[]>("/api/v1/canvases/menu"),
  saveCanvasMenu: (items: CanvasMenuItem[]) =>
    request<CanvasMenuItem[]>("/api/v1/canvases/menu", {
      method: "PUT",
      body: JSON.stringify(items),
    }),
  fetchProviderModelFolder: (id: number, folder: string) =>
    request<string[]>(`/api/v1/providers/${id}/models/${folder}`),

  getJob: (id: string) => request<JobOut>(`/api/v1/jobs/${id}`),
  listJobs: (kind?: string) =>
    request<JobOut[]>(`/api/v1/jobs?limit=10${kind ? `&kind=${kind}` : ""}`),
  listAllJobs: (statusFilter?: string) =>
    request<JobOut[]>(`/api/v1/jobs?limit=100${statusFilter ? `&status_filter=${statusFilter}` : ""}`),
  cancelJob: (id: string) => request<JobOut>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }),
  retryJob: (id: string) => request<JobOut>(`/api/v1/jobs/${id}/retry`, { method: "POST" }),
  deleteAsset: (id: number) => request<void>(`/api/v1/assets/${id}`, { method: "DELETE" }),
  getAsset: (id: number) => request<AssetOut>(`/api/v1/assets/${id}`),
  renameAsset: (id: number, name: string) =>
    request<AssetOut>(`/api/v1/assets/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),

  submitTts: (body: {
    provider_id?: number;
    voice_record_id?: number;
    voice?: string;
    text: string;
    format: string;
    model?: string;
    options?: { language?: string };
    workflow?: string;
    inputs?: Record<string, unknown>;
  }) => request<JobOut>("/api/v1/tts", { method: "POST", body: JSON.stringify(body) }),
  submitAsr: (form: FormData) =>
    request<JobOut>("/api/v1/asr", { method: "POST", body: form }),
  submitVc: (form: FormData) =>
    request<JobOut>("/api/v1/vc", { method: "POST", body: form }),
  listVoices: () => request<VoiceOut[]>("/api/v1/voices"),
  createVoice: (form: FormData) =>
    request<VoiceOut>("/api/v1/voices", { method: "POST", body: form }),
  deleteVoice: (id: number) => request<void>(`/api/v1/voices/${id}`, { method: "DELETE" }),
  setDefaultVoice: (id: number) =>
    request<VoiceOut>(`/api/v1/voices/${id}/default`, { method: "POST" }),
  listCharacters: () => request<CharacterOut[]>("/api/v1/characters"),
  createCharacter: (form: FormData) =>
    request<CharacterOut>("/api/v1/characters", { method: "POST", body: form }),
  generateCharacter: (form: FormData) =>
    request<JobOut>("/api/v1/characters/generate", { method: "POST", body: form }),
  deleteCharacter: (id: number) => request<void>(`/api/v1/characters/${id}`, { method: "DELETE" }),
  characterImage: (id: number, slot: string) =>
    requestBlob(`/api/v1/characters/${id}/image/${slot}`),
  registerCharacterAsset: (id: number, slot: string) =>
    request<AssetOut>(`/api/v1/characters/${id}/asset/${slot}`, { method: "POST" }),
  listAssets: (kind?: string, includeHidden?: boolean, jobFunction?: string) => {
    const qs = [
      kind && `kind=${encodeURIComponent(kind)}`,
      includeHidden && "include_hidden=true",
      jobFunction && `job_function=${encodeURIComponent(jobFunction)}`,
    ]
      .filter(Boolean)
      .join("&");
    return request<AssetOut[]>(`/api/v1/assets${qs ? `?${qs}` : ""}`);
  },
  listAssetJobs: (limit = 20, offset = 0, jobKind?: string) => {
    const qs = [
      `limit=${limit}`,
      `offset=${offset}`,
      jobKind && `job_kind=${encodeURIComponent(jobKind)}`,
    ]
      .filter(Boolean)
      .join("&");
    return request<AssetJobOut[]>(`/api/v1/assets/jobs?${qs}`);
  },
  listJobAssets: (jobId: string, limit = 50, offset = 0) =>
    request<AssetOut[]>(
      `/api/v1/assets?job_id=${encodeURIComponent(jobId)}&limit=${limit}&offset=${offset}`,
    ),
  getAssetDownloadUrl: (id: number) =>
    request<{ url: string }>(`/api/v1/assets/${id}/download-token`, { method: "POST" }).then(
      (result) => result.url,
    ),
  getAssetJobsDownloadUrl: (jobIds: string[]) =>
    request<{ url: string }>("/api/v1/assets/jobs/download-token", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds }),
    }).then((result) => result.url),
  deleteAssetJobs: (jobIds: string[]) =>
    request<{ jobs: number; assets: number }>("/api/v1/assets/jobs/delete", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds }),
    }),
  /** 发布画布中间结果：取消隐藏,资源库可见 */
  publishAsset: (id: number) =>
    request<AssetOut>(`/api/v1/assets/${id}/publish`, { method: "POST" }),

  listWorkflows: (capability?: string) =>
    request<WorkflowPackOut[]>(`/api/v1/workflows${capability ? `?capability=${capability}` : ""}`),
  importWorkflow: (body: Record<string, unknown>) =>
    request<WorkflowPackOut>("/api/v1/workflows/import", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteWorkflow: (name: string) =>
    request<void>(`/api/v1/workflows/${name}`, { method: "DELETE" }),
  updateWorkflow: (name: string, body: Record<string, unknown>) =>
    request<WorkflowPackOut>(`/api/v1/workflows/${name}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  exportWorkflow: (name: string) =>
    request<WorkflowPackBundle>(`/api/v1/workflows/${name}/export`),
  /** 画布或 API Format → LiberAstra 包草稿（不落盘） */
  convertWorkflow: (data: Record<string, unknown>) =>
    request<{
      workflow: Record<string, unknown>;
      capability: string;
      description: string;
      inputs: Record<string, WorkflowInputSpec>;
      outputs: Record<string, unknown>;
      requirements: Record<string, unknown>;
      fps?: number | null;
      accel?: WorkflowAccelSpec;
      source: string;
      warnings: string[];
      node_count: number;
      node_types: string[];
    }>("/api/v1/workflows/convert", {
      method: "POST",
      body: JSON.stringify({ data }),
    }),
  listTemplates: (aspect?: string, type?: string) => {
    const qs = [aspect && `aspect=${aspect}`, type && `type=${type}`].filter(Boolean).join("&");
    return request<TemplateOut[]>(`/api/v1/templates${qs ? `?${qs}` : ""}`);
  },
  uploadTemplate: (aspect: string, file: File) => {
    const form = new FormData();
    form.set("aspect", aspect);
    form.set("file", file);
    return request<TemplateOut>("/api/v1/templates", { method: "POST", body: form });
  },
  deleteTemplate: (aspect: string, name: string) =>
    request<void>(`/api/v1/templates/${aspect}/${name}`, { method: "DELETE" }),
  listBgm: () => request<BgmOut[]>("/api/v1/bgm"),
  uploadBgm: (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<BgmOut>("/api/v1/bgm", { method: "POST", body: form });
  },
  deleteBgm: (name: string) =>
    request<void>(`/api/v1/bgm/${encodeURIComponent(name)}`, { method: "DELETE" }),
  generateImage: (body: Record<string, unknown>) =>
    request<JobOut>("/api/v1/images/generate", { method: "POST", body: JSON.stringify(body) }),
  editImage: (form: FormData) =>
    request<JobOut>("/api/v1/images/edit", { method: "POST", body: form }),
  convertDepth: (form: FormData) =>
    request<AssetOut[]>("/api/v1/images/depth", { method: "POST", body: form }),
  listPlugins: () => request<PluginOut[]>("/api/v1/plugins"),
  installPlugin: (id: string, body?: { device?: string; models_dir?: string }) =>
    request<PluginOut>(`/api/v1/plugins/${id}/install`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  uninstallPlugin: (id: string) =>
    request<PluginOut>(`/api/v1/plugins/${id}/uninstall`, { method: "POST" }),
  enablePlugin: (id: string) =>
    request<PluginOut>(`/api/v1/plugins/${id}/enable`, { method: "POST" }),
  disablePlugin: (id: string) =>
    request<PluginOut>(`/api/v1/plugins/${id}/disable`, { method: "POST" }),
  listPrompts: () =>
    request<{ tasks: PromptTaskOut[]; scenes: PromptSceneOut[] }>("/api/v1/prompts"),
  /** 覆盖/新建功能模板；与内置一致时后端保持默认。 */
  putPromptTask: (id: string, body: { name: string; system: string; capabilities?: string[] }) =>
    request<{ status: string; id: string; origin: PromptOrigin }>(
      `/api/v1/prompts/tasks/${encodeURIComponent(id)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),
  deletePromptTask: (id: string, mode: "reset" | "delete" = "reset") =>
    request<void>(
      `/api/v1/prompts/tasks/${encodeURIComponent(id)}?mode=${mode}`,
      { method: "DELETE" },
    ),
  putPromptScene: (id: string, body: { name: string; append: string }) =>
    request<{ status: string; id: string; origin: PromptOrigin }>(
      `/api/v1/prompts/scenes/${encodeURIComponent(id)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),
  deletePromptScene: (id: string, mode: "reset" | "delete" = "reset") =>
    request<void>(
      `/api/v1/prompts/scenes/${encodeURIComponent(id)}?mode=${mode}`,
      { method: "DELETE" },
    ),
  importPrompts: (body: Record<string, unknown>) =>
    request<{ tasks: number; scenes: number }>("/api/v1/prompts/import", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  /** 提交 prompt.optimize Job（202）；刷新后凭 jobId 继续轮询 */
  optimizePrompt: (body: PromptOptimizeInput | string, provider_id?: number) => {
    const payload: PromptOptimizeInput =
      typeof body === "string" ? { prompt: body, task: "t2i", provider_id } : body;
    return request<JobOut>("/api/v1/prompts/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  uploadFile: (file: File) => {
    assertUploadSize(file);
    const form = new FormData();
    form.set("file", file);
    return request<{ path: string; size: number }>("/api/v1/uploads", {
      method: "POST",
      body: form,
    });
  },
  /** 上传并同时建档为资产（画布输入节点引用 assetId）;hidden=true 建档即隐藏(蒙版等中间产物) */
  uploadFileAsAsset: (file: File, kind: string, hidden = false) => {
    assertUploadSize(file);
    const form = new FormData();
    form.set("file", file);
    return request<{ path: string; size: number; asset_id: number }>(
      `/api/v1/uploads?as_asset=true&kind=${kind}${hidden ? "&hidden=true" : ""}`,
      { method: "POST", body: form },
    );
  },
  submitQuickVideo: (body: Record<string, unknown>) =>
    request<JobOut>("/api/v1/videos/quick", { method: "POST", body: JSON.stringify(body) }),
  submitVideoI2v: (form: FormData) =>
    request<JobOut>("/api/v1/videos/i2v", { method: "POST", body: form }),
  submitVideoEdit: (form: FormData) =>
    request<JobOut>("/api/v1/videos/edit", { method: "POST", body: form }),
  submitVideoAvatar: (form: FormData) =>
    request<JobOut>("/api/v1/videos/avatar", { method: "POST", body: form }),
  submitVideoMotion: (form: FormData) =>
    request<JobOut>("/api/v1/videos/motion", { method: "POST", body: form }),
  submitVideoAssets: (form: FormData) =>
    request<JobOut>("/api/v1/videos/assets", { method: "POST", body: form }),
  submitToolConcat: (body: Record<string, unknown>) =>
    request<JobOut>("/api/v1/tools/concat", { method: "POST", body: JSON.stringify(body) }),
  /** 看素材写口播（202）。结果是文本，确认后再走 submitVideoAssets。 */
  submitVideoAssetsScript: (form: FormData) =>
    request<JobOut>("/api/v1/videos/assets/script", { method: "POST", body: form }),

  // ---- 无限画布 ----
  listCanvases: () => request<CanvasListOut[]>("/api/v1/canvases"),
  createCanvas: (body: { name?: string; graph?: CanvasGraph }) =>
    request<CanvasOut>("/api/v1/canvases", { method: "POST", body: JSON.stringify(body) }),
  getCanvas: (id: string) => request<CanvasOut>(`/api/v1/canvases/${id}`),
  updateCanvas: (id: string, body: { name?: string; graph?: CanvasGraph }) =>
    request<CanvasOut>(`/api/v1/canvases/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  duplicateCanvas: (id: string) =>
    request<CanvasOut>(`/api/v1/canvases/${id}/duplicate`, { method: "POST" }),
  deleteCanvas: (id: string) =>
    request<void>(`/api/v1/canvases/${id}`, { method: "DELETE" }),
  /** 执行：node_ids 空 = 所有末端分支；force_node_ids 忽略指纹复用 */
  runCanvas: (id: string, body: { node_ids?: string[]; force_node_ids?: string[] }) =>
    request<CanvasRunOut>(`/api/v1/canvases/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  /** 强制重跑单个节点及其上游 */
  rerunCanvasNode: (id: string, nodeId: string) =>
    request<CanvasRunOut>(`/api/v1/canvases/${id}/nodes/${nodeId}/run`, { method: "POST" }),
  getCanvasRuns: (id: string) => request<CanvasRunOut>(`/api/v1/canvases/${id}/runs`),
  cancelCanvasRun: (id: string) =>
    request<CanvasRunCancelOut>(`/api/v1/canvases/${id}/run/cancel`, { method: "POST" }),
  getCanvasGroups: () => request<CanvasGroups>("/api/v1/canvases/groups"),
  putCanvasGroups: (groups: CanvasGroups) =>
    request<CanvasGroups>("/api/v1/canvases/groups", {
      method: "PUT",
      body: JSON.stringify(groups),
    }),

  // ---- 导演台 ----
  listAgentSessions: (canvasId?: string) =>
    request<AgentSessionOut[]>(
      `/api/v1/agent/sessions${canvasId ? `?canvas_id=${encodeURIComponent(canvasId)}` : ""}`,
    ),
  createAgentSession: (body: {
    canvas_id?: string | null;
    title?: string;
    provider_id?: number | null;
    model?: string;
    active_skill?: string;
  }) =>
    request<AgentSessionOut>("/api/v1/agent/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  patchAgentSession: (
    id: string,
    body: {
      title?: string;
      provider_id?: number | null;
      model?: string;
      active_skill?: string;
      use_default?: boolean;
    },
  ) =>
    request<AgentSessionOut>(`/api/v1/agent/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteAgentSession: (id: string) =>
    request<void>(`/api/v1/agent/sessions/${id}`, { method: "DELETE" }),
  listAgentMessages: (id: string) =>
    request<AgentMessageOut[]>(`/api/v1/agent/sessions/${id}/messages`),
  cancelAgentTurn: (id: string) =>
    request<{ ok: boolean }>(`/api/v1/agent/sessions/${id}/cancel`, { method: "POST" }),
  agentTurn: (
    id: string,
    body: AgentTurnInput,
    onEvent: (event: AgentSseEvent) => void,
    signal?: AbortSignal,
  ) => streamAgentEvents(`/api/v1/agent/sessions/${id}/turns`, body, onEvent, signal),
  agentToolResults: (
    id: string,
    body: {
      results: Record<string, unknown>[];
      approved?: boolean | null;
      remember?: boolean;
    },
    onEvent: (event: AgentSseEvent) => void,
    signal?: AbortSignal,
  ) =>
    streamAgentEvents(
      `/api/v1/agent/sessions/${id}/tool-results`,
      body,
      onEvent,
      signal,
    ),
  listAgentSkills: () => request<AgentSkillOut[]>("/api/v1/agent/skills"),
  getAgentSkill: (name: string) =>
    request<{
      name: string;
      description: string;
      body: string;
      license?: string;
      compatibility?: string;
      allowed_tools?: string[];
      files?: AgentSkillFileOut[];
    }>(`/api/v1/agent/skills/${encodeURIComponent(name)}`),
  uploadAgentSkill: (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<{ name: string }>("/api/v1/agent/skills", {
      method: "POST",
      body: form,
    });
  },
  setAgentSkillEnabled: (name: string, enabled: boolean) =>
    request<{ name: string; enabled: boolean }>(
      `/api/v1/agent/skills/${encodeURIComponent(name)}/enabled?enabled=${enabled}`,
      { method: "POST" },
    ),
  deleteAgentSkill: (name: string) =>
    request<void>(`/api/v1/agent/skills/${encodeURIComponent(name)}`, { method: "DELETE" }),
};

/** 带鉴权下载资产内容为 Blob（audio 标签无法带 Authorization 头）。 */
export async function fetchAssetBlob(assetId: number): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/assets/${assetId}/content`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `下载资产失败: ${resp.statusText}`);
  return resp.blob();
}

/** 带鉴权获取列表用缩略图（480px WebP）。原文件仍走 fetchAssetBlob。 */
export async function fetchAssetThumb(assetId: number): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  // reload：避开之前 immutable 缓存下来的彩色缩略图
  const resp = await fetch(`/api/v1/assets/${assetId}/thumb`, { headers, cache: "reload" });
  if (!resp.ok) throw new ApiError(resp.status, `缩略图失败: ${resp.statusText}`);
  return resp.blob();
}

/** 带鉴权获取模板预览图（后端缓存的 480px WebP）。 */
export async function fetchTemplatePreview(aspect: string, name: string): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/templates/${aspect}/${name}/preview`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `模板预览失败: ${resp.statusText}`);
  return resp.blob();
}

/** 本地 TTS / API TTS 短句试听。直接返回 mp3，不进入任务队列。 */
export async function previewTts(body: {
  provider_id: number;
  voice: string;
  text: string;
}): Promise<Blob> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch("/api/v1/tts/preview", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (resp.status === 401 && authToken && onUnauthorized) onUnauthorized();
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const payload = await resp.json();
      detail = payload.detail ?? detail;
    } catch {
      /* 非 JSON 响应 */
    }
    throw new ApiError(resp.status, String(detail));
  }
  return resp.blob();
}

/** 带鉴权获取音乐内容（audio 标签无法带 Authorization 头）。 */
export async function fetchBgmBlob(name: string): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/bgm/${encodeURIComponent(name)}/content`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `加载音乐失败: ${resp.statusText}`);
  return resp.blob();
}

/** 带鉴权获取音色库参考音频（audio 标签无法带 Authorization 头）。 */
export async function fetchVoiceRefBlob(voiceId: number): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/voices/${voiceId}/ref-audio`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `加载参考音频失败: ${resp.statusText}`);
  return resp.blob();
}

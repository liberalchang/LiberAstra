import type { components } from "./types";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  created_at: string;
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
  default_tts_model: string;
  default_asr_model: string;
}

export interface PromptTaskOut {
  id: string;
  name: string;
  capabilities: string[];
  system: string;
}

export interface PromptSceneOut {
  id: string;
  name: string;
  append: string;
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
}

export const TERMINAL_STATUSES = ["succeeded", "failed", "canceled"];

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

  submitTts: (body: {
    provider_id?: number;
    voice_record_id?: number;
    voice?: string;
    text: string;
    format: string;
    options?: { language?: string };
    workflow?: string;
    inputs?: Record<string, unknown>;
  }) => request<JobOut>("/api/v1/tts", { method: "POST", body: JSON.stringify(body) }),
  submitAsr: (form: FormData) =>
    request<JobOut>("/api/v1/asr", { method: "POST", body: form }),
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
  listAssets: (kind?: string) =>
    request<AssetOut[]>(`/api/v1/assets${kind ? `?kind=${kind}` : ""}`),

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
  listPrompts: () =>
    request<{ tasks: PromptTaskOut[]; scenes: PromptSceneOut[] }>("/api/v1/prompts"),
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
    const form = new FormData();
    form.set("file", file);
    return request<{ path: string; size: number }>("/api/v1/uploads", {
      method: "POST",
      body: form,
    });
  },
  submitQuickVideo: (body: Record<string, unknown>) =>
    request<JobOut>("/api/v1/videos/quick", { method: "POST", body: JSON.stringify(body) }),
  submitVideoI2v: (form: FormData) =>
    request<JobOut>("/api/v1/videos/i2v", { method: "POST", body: form }),
  submitVideoAvatar: (form: FormData) =>
    request<JobOut>("/api/v1/videos/avatar", { method: "POST", body: form }),
  submitVideoMotion: (form: FormData) =>
    request<JobOut>("/api/v1/videos/motion", { method: "POST", body: form }),
  submitVideoAssets: (form: FormData) =>
    request<JobOut>("/api/v1/videos/assets", { method: "POST", body: form }),
  /** 看素材写口播（202）。结果是文本，确认后再走 submitVideoAssets。 */
  submitVideoAssetsScript: (form: FormData) =>
    request<JobOut>("/api/v1/videos/assets/script", { method: "POST", body: form }),
};

/** 带鉴权下载资产内容为 Blob（audio 标签无法带 Authorization 头）。 */
export async function fetchAssetBlob(assetId: number): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/assets/${assetId}/content`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `下载资产失败: ${resp.statusText}`);
  return resp.blob();
}

/** 带鉴权获取模板预览图（渲染由后端 Playwright 完成，返回 jpeg）。 */
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

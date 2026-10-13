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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const resp = await fetch(path, { ...init, headers });
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
}

export interface JobOut {
  id: string;
  kind: string;
  status: "pending" | "running" | "succeeded" | "failed" | "canceled";
  progress: number;
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

export interface AssetOut {
  id: number;
  kind: string;
  mime: string | null;
  size: number;
  job_id: string | null;
  meta: Record<string, unknown>;
  created_at: string;
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
}

export interface WorkflowPackOut {
  name: string;
  capability: string;
  description: string;
  inputs: Record<string, WorkflowInputSpec>;
  outputs: Record<string, unknown>;
  source: string;
  requirements: Record<string, unknown>;
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

  getJob: (id: string) => request<JobOut>(`/api/v1/jobs/${id}`),
  listJobs: (kind?: string) =>
    request<JobOut[]>(`/api/v1/jobs?limit=10${kind ? `&kind=${kind}` : ""}`),

  submitTts: (body: {
    provider_id?: number;
    voice_record_id?: number;
    voice?: string;
    text: string;
    format: string;
  }) => request<JobOut>("/api/v1/tts", { method: "POST", body: JSON.stringify(body) }),
  submitAsr: (form: FormData) =>
    request<JobOut>("/api/v1/asr", { method: "POST", body: form }),
  listVoices: () => request<VoiceOut[]>("/api/v1/voices"),
  createVoice: (form: FormData) =>
    request<VoiceOut>("/api/v1/voices", { method: "POST", body: form }),
  deleteVoice: (id: number) => request<void>(`/api/v1/voices/${id}`, { method: "DELETE" }),
  setDefaultVoice: (id: number) =>
    request<VoiceOut>(`/api/v1/voices/${id}/default`, { method: "POST" }),
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
  generateImage: (body: Record<string, unknown>) =>
    request<JobOut>("/api/v1/images/generate", { method: "POST", body: JSON.stringify(body) }),
  editImage: (form: FormData) =>
    request<JobOut>("/api/v1/images/edit", { method: "POST", body: form }),
  optimizePrompt: (prompt: string, provider_id?: number) =>
    request<{ optimized: string }>("/api/v1/images/optimize-prompt", {
      method: "POST",
      body: JSON.stringify({ prompt, provider_id }),
    }),

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
};

/** 带鉴权下载资产内容为 Blob（audio 标签无法带 Authorization 头）。 */
export async function fetchAssetBlob(assetId: number): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`/api/v1/assets/${assetId}/content`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `下载资产失败: ${resp.statusText}`);
  return resp.blob();
}

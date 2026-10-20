import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function formatTime(iso: string): string {
  return iso.slice(0, 19).replace("T", " ");
}

/** 计算资产展示/下载名所需的最小字段集（与 AssetOut 结构兼容）。 */
export interface AssetNameSource {
  path: string;
  created_at?: string;
  meta?: Record<string, unknown> | null;
}

export function assetBaseName(path: string): string {
  return path.split("/").pop() ?? path;
}

/** 资产内容摘要：提示词 / 文案 / 标题，用于展示与下载命名。 */
export function assetSummary(meta?: Record<string, unknown> | null): string | null {
  const v = meta?.prompt ?? meta?.text ?? meta?.title;
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

/** 资产卡片/列表的显示名：优先内容摘要，回落到落盘文件名。 */
export function assetTitle(a: AssetNameSource, maxLen = 24): string {
  const s = assetSummary(a.meta);
  if (!s) return assetBaseName(a.path);
  return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
}

/** 下载文件名：`YYYYMMDD_摘要.ext`，无摘要时保持落盘文件名。 */
export function assetDownloadName(a: AssetNameSource): string {
  const base = assetBaseName(a.path);
  const s = assetSummary(a.meta);
  if (!s) return base;
  const ext = base.includes(".") ? base.slice(base.lastIndexOf(".")) : "";
  const date = (a.created_at ?? "").slice(0, 10).replaceAll("-", "");
  const slug = s.replace(/[\\/:*?"<>|\s]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24);
  return slug ? `${date}_${slug}${ext}` : base;
}

/** 后端任务步骤标识 → 中文。未收录的原样返回。 */
const STEP_LABELS: Record<string, string> = {
  script: "写口播文案",
  narration: "写口播文案",
  storyboard: "生成分镜",
  generate: "生成图像",
  edit: "图像处理",
  synthesize: "合成语音",
  transcribe: "识别语音",
  tts: "配音合成",
  comfyui: "ComfyUI 执行中",
  concat: "拼接分段",
  bgm: "混入背景音乐",
  chat: "对话生成",
};

/** 后端任务步骤名转中文展示，支持 "frame 2/4"、"frame 2/4 配音" 这类逐镜格式。 */
export function formatStepName(
  name: string,
  tx: (zh: string, vars?: Record<string, string | number>) => string = (zh) => zh,
): string {
  const m = /^frame\s+(\d+)\/(\d+)(?:\s+(.*))?$/.exec(name);
  if (m) {
    const base = tx("第 {a}/{b} 镜", { a: m[1], b: m[2] });
    return m[3] ? `${base} · ${tx(STEP_LABELS[m[3]] ?? m[3])}` : base;
  }
  return tx(STEP_LABELS[name] ?? name);
}

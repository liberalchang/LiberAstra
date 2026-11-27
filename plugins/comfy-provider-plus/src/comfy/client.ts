import { randomUUID } from "node:crypto";
import { createComfyError, classifyFetchFailure, formatExecutionError, redactSensitive } from "./errors.js";
import type { ComfyPrompt, InputImage } from "../types.js";

export type ComfyClientOptions = {
  baseUrl: string;
  timeoutMs: number;
  pollIntervalMs: number;
  maxUploadBytes: number;
  /** 单次 history 轮询短超时，默认 20s */
  pollRequestTimeoutMs?: number;
  fetchImpl?: typeof fetch;
  /** 可注入时钟，便于 600s 超时单测 */
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
};

export type UploadResult = {
  filename: string;
  index: number;
};

const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
const JPEG_SIG = Buffer.from([0xff, 0xd8, 0xff]);
const WEBP_SIG = Buffer.from("WEBP");

function detectImageExt(buffer: Buffer, mimeType: string, fileName?: string): string {
  if (buffer.length >= 4 && buffer.subarray(0, 4).equals(PNG_SIG)) return "png";
  if (buffer.length >= 3 && buffer.subarray(0, 3).equals(JPEG_SIG)) return "jpg";
  if (buffer.length >= 12 && buffer.subarray(8, 12).equals(WEBP_SIG)) return "webp";
  if (mimeType.includes("png")) return "png";
  if (mimeType.includes("jpeg") || mimeType.includes("jpg")) return "jpg";
  if (mimeType.includes("webp")) return "webp";
  const fromName = fileName?.split(".").pop()?.toLowerCase();
  if (fromName && ["png", "jpg", "jpeg", "webp", "gif", "webp"].includes(fromName)) {
    return fromName === "jpeg" ? "jpg" : fromName;
  }
  throw createComfyError("UPLOAD_FAILED", "不支持的图片格式（魔数/MIME 校验失败）", {
    index: 0,
  });
}

function safeBaseName(name: string | undefined): string {
  const base = (name ?? "image").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 64);
  return base || "image";
}

export class ComfyClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly pollIntervalMs: number;
  private readonly maxUploadBytes: number;
  private readonly pollRequestTimeoutMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly now: () => number;
  private readonly sleep: (ms: number) => Promise<void>;

  constructor(opts: ComfyClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs;
    this.pollIntervalMs = opts.pollIntervalMs;
    this.maxUploadBytes = opts.maxUploadBytes;
    this.pollRequestTimeoutMs = opts.pollRequestTimeoutMs ?? 20_000;
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.now = opts.now ?? Date.now;
    this.sleep = opts.sleep ?? sleep;
  }

  /** 本地全量预检：任一张失败则不发网络请求 */
  preflightImages(images: InputImage[]): void {
    if (images.length === 0) return;
    images.forEach((img, i) => {
      const index = i + 1;
      if (!img.buffer || img.buffer.length === 0) {
        throw createComfyError("UPLOAD_FAILED", `第 ${index} 张图片为空文件`, { index });
      }
      if (img.buffer.length > this.maxUploadBytes) {
        throw createComfyError(
          "UPLOAD_FAILED",
          `第 ${index} 张图片超过大小上限 ${this.maxUploadBytes} bytes`,
          { index },
        );
      }
      try {
        detectImageExt(img.buffer, img.mimeType, img.fileName);
      } catch (err) {
        throw createComfyError(
          "UPLOAD_FAILED",
          `第 ${index} 张图片格式无效: ${err instanceof Error ? err.message : String(err)}`,
          { index },
        );
      }
    });
  }

  /**
   * 顺序上传；第 k 张失败则中止整次请求（事务性）。
   */
  async uploadImages(images: InputImage[], reqId = randomUUID().slice(0, 8)): Promise<UploadResult[]> {
    this.preflightImages(images);
    const out: UploadResult[] = [];
    for (let i = 0; i < images.length; i += 1) {
      const index = i + 1;
      const img = images[i];
      const ext = detectImageExt(img.buffer, img.mimeType, img.fileName);
      const filename = `ocp_${reqId}_img${String(index).padStart(2, "0")}_${safeBaseName(img.fileName)}.${ext}`;
      try {
        const form = new FormData();
        form.set(
          "image",
          new Blob([img.buffer], { type: img.mimeType || `image/${ext}` }),
          filename,
        );
        form.set("type", "input");
        form.set("overwrite", "true");
        const res = await this.fetchImpl(`${this.baseUrl}/upload/image`, {
          method: "POST",
          body: form,
          signal: AbortSignal.timeout(Math.min(this.timeoutMs, 120_000)),
        });
        if (!res.ok) {
          const body = redactSensitive(await res.text().catch(() => ""));
          throw createComfyError(
            "UPLOAD_FAILED",
            `第 ${index} 张上传失败: HTTP ${res.status} ${body}`,
            { index },
          );
        }
        const payload = (await res.json()) as { name?: string; filename?: string };
        const uploaded = payload.name || payload.filename;
        if (!uploaded) {
          throw createComfyError("UPLOAD_FAILED", `第 ${index} 张上传响应缺少 filename`, {
            index,
          });
        }
        out.push({ filename: uploaded, index });
      } catch (err) {
        if (err && typeof err === "object" && "code" in err) throw err;
        throw classifyFetchFailure(err, `第 ${index} 张上传`);
      }
    }
    return out;
  }

  async submitPrompt(prompt: ComfyPrompt): Promise<string> {
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
        signal: AbortSignal.timeout(Math.min(this.timeoutMs, 60_000)),
      });
      if (!res.ok) {
        const body = redactSensitive(await res.text().catch(() => ""));
        throw createComfyError("EXECUTION_FAILED", `提交工作流失败: HTTP ${res.status} ${body}`);
      }
      const payload = (await res.json()) as { prompt_id?: string; error?: unknown };
      if (!payload.prompt_id) {
        throw createComfyError(
          "EXECUTION_FAILED",
          `提交响应缺少 prompt_id: ${formatExecutionError(payload.error ?? payload)}`,
        );
      }
      return payload.prompt_id;
    } catch (err) {
      if (err && typeof err === "object" && "code" in err) throw err;
      throw classifyFetchFailure(err, "提交工作流");
    }
  }

  async waitForHistory(promptId: string): Promise<Record<string, unknown>> {
    const deadline = this.now() + this.timeoutMs;
    while (this.now() < deadline) {
      const remaining = deadline - this.now();
      if (remaining <= 0) break;
      try {
        const res = await this.fetchImpl(`${this.baseUrl}/history/${promptId}`, {
          method: "GET",
          signal: AbortSignal.timeout(Math.min(this.pollRequestTimeoutMs, remaining)),
        });
        if (!res.ok) {
          // 瞬时失败：重试至总 deadline
          await this.sleep(Math.min(this.pollIntervalMs, remaining));
          continue;
        }
        const history = (await res.json()) as Record<string, unknown>;
        const entry = (history[promptId] ?? history) as Record<string, unknown>;
        const status = entry.status as { status_str?: string; completed?: boolean; messages?: unknown } | undefined;
        if (status?.status_str === "error") {
          const messages = Array.isArray(status.messages) ? status.messages : [];
          const errMsg = messages.find(
            (m) => Array.isArray(m) && m[0] === "execution_error",
          ) as unknown[] | undefined;
          const detail = errMsg?.[1];
          throw createComfyError(
            "EXECUTION_FAILED",
            `工作流执行失败: ${formatExecutionError(detail)}`,
          );
        }
        if (status?.completed === true || (entry.outputs && Object.keys(entry.outputs as object).length)) {
          return entry;
        }
      } catch (err) {
        if (err && typeof err === "object" && "code" in err) throw err;
        // 瞬时网络/超时：继续直到总 deadline
      }
      const remainingAfter = deadline - this.now();
      if (remainingAfter <= 0) break;
      await this.sleep(Math.min(this.pollIntervalMs, remainingAfter));
    }
    await this.tryCleanup(promptId);
    throw createComfyError(
      "EXECUTION_TIMEOUT",
      `Comfy 工作流未在 ${Math.ceil(this.timeoutMs / 1000)}s 内完成`,
      { promptId, timeoutMs: this.timeoutMs },
    );
  }

  async downloadOutput(
    file: { filename?: string; name?: string; subfolder?: string; type?: string },
  ): Promise<{ buffer: Buffer; mimeType: string; fileName: string }> {
    const fileName = file.filename || file.name;
    if (!fileName) throw createComfyError("EXECUTION_FAILED", "输出缺少 filename");
    const query = new URLSearchParams({
      filename: fileName,
      subfolder: file.subfolder ?? "",
      type: file.type ?? "output",
    });
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/view?${query}`, {
        method: "GET",
        signal: AbortSignal.timeout(Math.min(this.timeoutMs, 120_000)),
      });
      if (!res.ok) {
        throw createComfyError("EXECUTION_FAILED", `下载输出失败: HTTP ${res.status}`);
      }
      const mimeType = res.headers.get("content-type") || "application/octet-stream";
      const ab = await res.arrayBuffer();
      return { buffer: Buffer.from(ab), mimeType, fileName };
    } catch (err) {
      if (err && typeof err === "object" && "code" in err) throw err;
      throw classifyFetchFailure(err, "下载输出");
    }
  }

  extractImages(
    historyEntry: Record<string, unknown>,
    outputNodeId?: string,
  ): Array<{ filename?: string; name?: string; subfolder?: string; type?: string; nodeId: string }> {
    const outputs = historyEntry.outputs as Record<string, Record<string, unknown>> | undefined;
    if (!outputs) return [];
    const nodeIds = outputNodeId ? [outputNodeId] : Object.keys(outputs);
    const files: Array<{ filename?: string; name?: string; subfolder?: string; type?: string; nodeId: string }> = [];
    for (const nodeId of nodeIds) {
      const bucket = outputs[nodeId]?.images;
      if (!Array.isArray(bucket)) continue;
      for (const file of bucket) {
        if (file && typeof file === "object") {
          files.push({ ...(file as object), nodeId } as never);
        }
      }
    }
    return files;
  }

  private async tryCleanup(promptId: string): Promise<void> {
    try {
      await this.fetchImpl(`${this.baseUrl}/queue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delete: [promptId] }),
        signal: AbortSignal.timeout(5_000),
      });
    } catch {
      /* 尽力清理 */
    }
    try {
      await this.fetchImpl(`${this.baseUrl}/interrupt`, {
        method: "POST",
        signal: AbortSignal.timeout(5_000),
      });
    } catch {
      /* 尽力清理 */
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

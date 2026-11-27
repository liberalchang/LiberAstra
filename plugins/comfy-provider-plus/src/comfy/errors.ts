import type { ComfyErrorCode, ComfyPlusError } from "../types.js";

const PATH_RE =
  /(?:[A-Za-z]:\\|\\\\|\/(?:Users|home|root|var|tmp|private)\/)[^\s"'`]+/g;
const SECRET_RE =
  /(?:api[_-]?key|token|authorization|bearer|secret|password)\s*[:=]\s*["']?[^\s"',}]+/gi;

/** 剥离密钥、Token、本机绝对路径与堆栈噪声 */
export function redactSensitive(text: string): string {
  return text
    .replace(SECRET_RE, "[REDACTED_SECRET]")
    .replace(PATH_RE, "[REDACTED_PATH]")
    .replace(/\n\s*at\s+[^\n]+/g, "")
    .trim();
}

export function createComfyError(
  code: ComfyErrorCode,
  message: string,
  details?: Record<string, unknown>,
): ComfyPlusError {
  const err = new Error(redactSensitive(message)) as ComfyPlusError;
  err.code = code;
  if (details) {
    err.details = JSON.parse(redactSensitive(JSON.stringify(details))) as Record<string, unknown>;
  }
  return err;
}

export function classifyFetchFailure(err: unknown, context: string): ComfyPlusError {
  const msg = err instanceof Error ? err.message : String(err);
  const lower = msg.toLowerCase();
  if (
    lower.includes("econnrefused") ||
    lower.includes("enotfound") ||
    lower.includes("fetch failed") ||
    lower.includes("network") ||
    lower.includes("unreachable") ||
    lower.includes("econnreset")
  ) {
    return createComfyError("COMFY_UNREACHABLE", `ComfyUI 不可达（${context}）: ${msg}`);
  }
  return createComfyError("EXECUTION_FAILED", `${context}: ${msg}`);
}

export function formatExecutionError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "执行失败";
  const rec = payload as Record<string, unknown>;
  const nodeType = typeof rec.node_type === "string" ? rec.node_type : undefined;
  const nodeId = rec.node_id != null ? String(rec.node_id) : undefined;
  const exception =
    typeof rec.exception_message === "string"
      ? rec.exception_message
      : typeof rec.message === "string"
        ? rec.message
        : undefined;
  const parts = [
    nodeType ? `node_type=${nodeType}` : undefined,
    nodeId ? `node_id=${nodeId}` : undefined,
    exception ? redactSensitive(exception) : undefined,
  ].filter(Boolean);
  return parts.length ? parts.join("; ") : "执行失败";
}

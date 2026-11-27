import type { ComfyErrorCode, ComfyPlusError } from "../types.js";

const PATH_RE =
  /(?:[A-Za-z]:[\\/][^\s"'`,}\]]+|\\\\[^\s"'`,}\]]+|\/(?:Users|home|root|var|tmp|private|etc|opt|srv|mnt|Volumes)\/[^\s"'`,}\]]+)/g;

const AUTH_BEARER_RE = /Authorization\s*:\s*Bearer\s+\S+/gi;
const BARE_BEARER_RE = /\bBearer\s+\S+/gi;
const URL_CRED_RE = /:\/\/[^/\s:@]+:[^/\s@]+@/gi;
const SECRET_KV_RE =
  /(?:api[_-]?key|token|secret|password|authorization)\s*[:=]\s*["']?[^\s"',}\]]+/gi;

const SENSITIVE_KEY_RE = /^(?:api[_-]?key|token|secret|password|authorization|bearer|auth)$/i;

/** 剥离密钥、Token、本机绝对路径与堆栈噪声 */
export function redactSensitive(text: string): string {
  return text
    .replace(AUTH_BEARER_RE, "[REDACTED_SECRET]")
    .replace(BARE_BEARER_RE, "[REDACTED_SECRET]")
    .replace(URL_CRED_RE, "://[REDACTED_SECRET]@")
    .replace(SECRET_KV_RE, "[REDACTED_SECRET]")
    .replace(PATH_RE, "[REDACTED_PATH]")
    .replace(/\n\s*at\s+[^\n]+/g, "")
    .trim();
}

function redactValue(value: unknown): unknown {
  if (typeof value === "string") return redactSensitive(value);
  if (Array.isArray(value)) return value.map(redactValue);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEY_RE.test(k)) {
        out[k] = "[REDACTED_SECRET]";
      } else {
        out[k] = redactValue(v);
      }
    }
    return out;
  }
  return value;
}

export function createComfyError(
  code: ComfyErrorCode,
  message: string,
  details?: Record<string, unknown>,
): ComfyPlusError {
  const err = new Error(redactSensitive(message)) as ComfyPlusError;
  err.code = code;
  if (details) {
    err.details = redactValue(details) as Record<string, unknown>;
  }
  return err;
}

export function classifyFetchFailure(
  err: unknown,
  context: string,
  extras?: { index?: number; preferUpload?: boolean },
): ComfyPlusError {
  const msg = err instanceof Error ? err.message : String(err);
  const name = err instanceof Error ? err.name : "";
  const lower = msg.toLowerCase();
  const details = extras?.index != null ? { index: extras.index } : undefined;

  if (
    name === "TimeoutError" ||
    name === "AbortError" ||
    lower.includes("aborted") ||
    lower.includes("timeout") ||
    lower.includes("timed out")
  ) {
    return createComfyError(
      "EXECUTION_TIMEOUT",
      `${context} 超时: ${msg}`,
      details,
    );
  }

  if (
    lower.includes("econnrefused") ||
    lower.includes("enotfound") ||
    lower.includes("fetch failed") ||
    lower.includes("network") ||
    lower.includes("unreachable") ||
    lower.includes("econnreset")
  ) {
    return createComfyError("COMFY_UNREACHABLE", `ComfyUI 不可达（${context}）: ${msg}`, details);
  }

  if (extras?.preferUpload) {
    return createComfyError("UPLOAD_FAILED", `${context}: ${msg}`, details);
  }

  return createComfyError("EXECUTION_FAILED", `${context}: ${msg}`, details);
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

/** 提示词双缓冲结构（原始 / 优化），供持久化与提交共用。 */

export type PromptFieldValue = {
  raw: string;
  optimized: string;
  /** 生成 optimized 时对应的 raw 快照；用于判断是否过期 */
  optimizedFromRaw: string;
  useOptimized: boolean;
};

export function emptyPromptValue(raw = ""): PromptFieldValue {
  return { raw, optimized: "", optimizedFromRaw: "", useOptimized: false };
}

/** 把 localStorage 里可能是旧版 string 或残缺对象的值规范成 PromptFieldValue */
export function coercePromptValue(raw: unknown): PromptFieldValue {
  if (typeof raw === "string") return emptyPromptValue(raw);
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    if ("raw" in o || "optimized" in o) {
      return {
        raw: String(o.raw ?? ""),
        optimized: String(o.optimized ?? ""),
        optimizedFromRaw: String(o.optimizedFromRaw ?? ""),
        useOptimized: Boolean(o.useOptimized),
      };
    }
  }
  return emptyPromptValue();
}

/** 提交时实际生效的提示词 */
export function resolveEffectivePrompt(v: PromptFieldValue): string {
  if (v.useOptimized && v.optimized.trim()) return v.optimized.trim();
  return v.raw.trim();
}

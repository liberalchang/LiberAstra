import type { WorkflowInputSpec } from "@/api/client";

/**
 * 从工作流包 inputs 取出 options_from（模型下拉）的默认文件名。
 * 换包且该包尚无本地存档时，用此初始化 extra，避免空值或沿用旧包模型。
 */
export function modelDefaultsFromInputs(
  inputs: Record<string, WorkflowInputSpec> | undefined,
  exclude: string[] = [],
): Record<string, string> {
  if (!inputs) return {};
  const skip = new Set(exclude);
  const out: Record<string, string> = {};
  for (const [key, spec] of Object.entries(inputs)) {
    if (skip.has(key)) continue;
    if (!spec.options_from || spec.default == null || spec.default === "") continue;
    out[key] = String(spec.default);
  }
  return out;
}

import type { WorkflowAccelSpec, WorkflowInputSpec } from "@/api/client";

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

/**
 * 展示加速开启时实际生效的参数。
 * 缺省、空值、或仍等于包默认值的参数由 accel.preset 覆盖；
 * 用户改成非默认值的参数保留。
 */
export function applyAccelPreset(
  values: Record<string, string>,
  accelSpec: WorkflowAccelSpec | null | undefined,
  inputs?: Record<string, WorkflowInputSpec>,
): Record<string, string> {
  const preset = accelSpec?.preset;
  if (!preset) return values;
  let changed = false;
  const out = { ...values };
  for (const [key, onValue] of Object.entries(preset)) {
    const def = inputs?.[key]?.default;
    const cur = out[key];
    if (cur !== undefined && cur !== "" && (def == null || String(cur) !== String(def))) {
      continue;
    }
    out[key] = String(onValue);
    changed = true;
  }
  return changed ? out : values;
}

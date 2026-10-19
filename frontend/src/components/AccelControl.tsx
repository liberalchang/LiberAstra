import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type WorkflowAccelSpec } from "@/api/client";
import { Field, selectClass } from "@/components/ui/field";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";

export type AccelState = {
  enabled: boolean;
  lora: string;
  strength: number;
};

/** 包是否声明了可用的加速能力。 */
export function hasAccel(accel?: WorkflowAccelSpec | null): boolean {
  return !!(accel && accel.node);
}

/** 把表单参数与 __accel 合并成提交用的 inputs 对象。 */
export function buildInputsWithAccel(
  values: Record<string, string>,
  accelSpec: WorkflowAccelSpec | undefined | null,
  accel: AccelState,
): Record<string, unknown> {
  const base: Record<string, unknown> = Object.fromEntries(
    Object.entries(values).filter(([, v]) => v !== ""),
  );
  if (!hasAccel(accelSpec)) return base;
  base.__accel = {
    enabled: accel.enabled,
    ...(accel.enabled
      ? {
          lora: accel.lora,
          strength: accel.strength,
        }
      : {}),
  };
  return base;
}

/** 从 accel 声明生成初始状态。 */
export function defaultAccelState(accel?: WorkflowAccelSpec | null): AccelState {
  const strengthDefault = accel?.strength?.default ?? 1;
  return {
    enabled: !!accel?.default_enabled,
    lora: accel?.lora?.recommended ?? "",
    strength: typeof strengthDefault === "number" ? strengthDefault : 1,
  };
}

type Props = {
  accel: WorkflowAccelSpec;
  providerId?: number;
  value: AccelState;
  onChange: (next: AccelState) => void;
  /** 开启加速时，把 preset 填入尚未设置的工作流参数（用户已填的不动）。 */
  onApplyPreset?: (preset: Record<string, string>) => void;
};

/** Turbo 加速开关 + LoRA 下拉 + 强度；仅在包声明了 accel 时渲染。 */
export function AccelControl({ accel, providerId, value, onChange, onApplyPreset }: Props) {
  const folder = accel.lora?.options_from ?? "loras";
  const match = (accel.lora?.match ?? "").toLowerCase();
  const recommended = accel.lora?.recommended ?? "";

  const { data, isLoading, isError } = useQuery({
    queryKey: ["provider-model-folder", providerId, folder],
    queryFn: () => api.fetchProviderModelFolder(providerId!, folder),
    enabled: providerId != null && value.enabled,
    staleTime: 60_000,
  });

  const raw = [...new Set(data ?? [])];
  const filtered = match
    ? raw.filter((n) => n.toLowerCase().includes(match))
    : raw;
  const recStem = recommended.replace(/\.safetensors$/i, "");
  const preferred = recommended
    ? filtered.filter((n) => n === recommended || (recStem.length > 0 && n.includes(recStem)))
    : [];
  const rest = filtered.filter((n) => !preferred.includes(n));
  const options = [...preferred, ...rest];

  // 开启后若还没选 LoRA，自动选推荐项或列表第一项
  useEffect(() => {
    if (!value.enabled || value.lora || options.length === 0) return;
    const pick = options.includes(recommended) ? recommended : options[0];
    if (pick) onChange({ ...value, lora: pick });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.enabled, value.lora, options, recommended]);

  const setEnabled = (on: boolean) => {
    onChange({ ...value, enabled: on });
    if (on && accel.preset && onApplyPreset) {
      const preset: Record<string, string> = {};
      for (const [k, v] of Object.entries(accel.preset)) {
        preset[k] = String(v);
      }
      onApplyPreset(preset);
    }
  };

  const strengthMin = accel.strength?.min ?? 0.5;
  const strengthMax = accel.strength?.max ?? 1.5;
  const label = accel.label ?? "Turbo 加速";

  return (
    <div className="flex flex-col gap-3 rounded-[10px] border border-border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">{label}</span>
          <span className="text-xs text-muted-foreground">
            {value.enabled ? "少步数采样，推荐 6–8 步" : "关闭时从图中摘掉加速 LoRA 节点"}
          </span>
        </div>
        <Segmented
          ariaLabel={label}
          value={value.enabled ? "on" : "off"}
          onChange={(v) => setEnabled(v === "on")}
          options={[
            { value: "off", label: "关闭" },
            { value: "on", label: "开启" },
          ]}
        />
      </div>

      {value.enabled && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="加速模型" hint={match ? `仅显示含「${accel.lora?.match}」的 LoRA` : undefined}>
            {providerId == null || isError ? (
              <input
                className={selectClass}
                type="text"
                value={value.lora}
                placeholder={recommended || "xxx.safetensors"}
                onChange={(e) => onChange({ ...value, lora: e.target.value })}
              />
            ) : (
              <select
                className={selectClass}
                value={value.lora}
                disabled={isLoading}
                onChange={(e) => onChange({ ...value, lora: e.target.value })}
              >
                {isLoading && <option value="">加载中…</option>}
                {!isLoading && value.lora && !options.includes(value.lora) && (
                  <option value={value.lora}>{value.lora}（不在列表中）</option>
                )}
                {preferred.length > 0 && rest.length > 0 ? (
                  <>
                    <optgroup label="推荐">
                      {preferred.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="全部匹配">
                      {rest.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </optgroup>
                  </>
                ) : (
                  options.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                )}
              </select>
            )}
          </Field>
          <Field label="加速强度" hint="拖影可上调，过锐可下调">
            <NumberStepper
              value={value.strength}
              min={strengthMin}
              max={strengthMax}
              step={0.05}
              onChange={(n) => onChange({ ...value, strength: n })}
              ariaLabel="加速强度"
            />
          </Field>
        </div>
      )}
    </div>
  );
}

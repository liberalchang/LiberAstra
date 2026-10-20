import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type WorkflowAccelSpec } from "@/api/client";
import { Field, selectClass } from "@/components/ui/field";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

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

/** LoRA 开关（Turbo / Uncensored 等）+ 文件下拉 + 强度；仅在包声明了 accel 时渲染。 */
export function AccelControl({ accel, providerId, value, onChange, onApplyPreset }: Props) {
  const tx = useTx();
  const folder = accel.lora?.options_from ?? "loras";
  const match = (accel.lora?.match ?? "").toLowerCase();
  const recommended = accel.lora?.recommended ?? "";
  const isTurbo = (accel.family ?? "").includes("minimax") || (accel.label ?? "").toLowerCase().includes("turbo");

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

  // 开启后：未选、或已选文件不在当前过滤结果里（例如旧的 T8 文件名）时，改选推荐项
  useEffect(() => {
    if (!value.enabled) return;
    const lora = value.lora ?? "";
    const matchesFilter = !match || lora.toLowerCase().includes(match);
    const listed = lora && options.includes(lora);
    if (lora && matchesFilter && (options.length === 0 || listed)) return;
    const pick =
      (recommended && options.includes(recommended) && recommended) ||
      (options.length > 0 ? options[0] : "") ||
      recommended;
    if (pick && pick !== lora) onChange({ ...value, lora: pick });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.enabled, value.lora, options, recommended, match]);

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

  const strengthMin = accel.strength?.min ?? 0;
  const strengthMax = accel.strength?.max ?? 1.5;
  const label = tx(accel.label ?? tx("Turbo 加速"));
  const hintOn = tx(
    accel.hint ?? (isTurbo ? tx("少步数采样，推荐 6–8 步") : tx("开启后把 LoRA 挂到主模型上")),
  );
  const hintOff = tx(
    accel.hint_off ?? (isTurbo ? tx("关闭时从图中摘掉加速 LoRA 节点") : tx("关闭时从图中摘掉 LoRA 节点")),
  );
  const loraLabel = tx(accel.lora_label ?? (isTurbo ? tx("加速模型") : tx("LoRA 文件")));
  const strengthLabel = tx(accel.strength_label ?? (isTurbo ? tx("加速强度") : tx("LoRA 强度")));

  return (
    <div className="flex flex-col gap-3 rounded-[10px] border border-border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">{label}</span>
          <span className="text-xs text-muted-foreground">
            {value.enabled ? hintOn : hintOff}
          </span>
        </div>
        <Segmented
          ariaLabel={label}
          value={value.enabled ? "on" : "off"}
          onChange={(v) => setEnabled(v === "on")}
          options={[
            { value: "off", label: tx("关闭") },
            { value: "on", label: tx("开启") },
          ]}
        />
      </div>

      {value.enabled && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={loraLabel} hint={match ? tx("仅显示含「{match}」的 LoRA", { match: accel.lora?.match ?? "" }) : undefined}>
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
                {isLoading && <option value="">{tx("加载中…")}</option>}
                {!isLoading && value.lora && !options.includes(value.lora) && (
                  <option value={value.lora}>{value.lora}{tx("（不在列表中）")}</option>
                )}
                {preferred.length > 0 && rest.length > 0 ? (
                  <>
                    <optgroup label={tx("推荐")}>
                      {preferred.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label={tx("全部匹配")}>
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
          <Field
            label={strengthLabel}
            hint={isTurbo ? tx("拖影可上调，过锐可下调") : tx("1.0 为推荐；过高可能过拟合")}
          >
            <NumberStepper
              value={value.strength}
              min={strengthMin}
              max={strengthMax}
              step={0.05}
              onChange={(n) => onChange({ ...value, strength: n })}
              ariaLabel={strengthLabel}
            />
          </Field>
        </div>
      )}
    </div>
  );
}

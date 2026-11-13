import { RotateCcw } from "lucide-react";

import { Switch } from "@/components/SpeechControls";
import { useTx } from "@/i18n/tx";
import {
  DEFAULT_TTS_TUNING,
  TTS_PRESETS,
  type TtsPreset,
  type TtsTuning as TtsTuningValue,
  tuningAt,
  tuningFromPreset,
} from "@/lib/ttsTuning";
import { cn } from "@/lib/utils";

function Range({
  label,
  value,
  min,
  max,
  step,
  display,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <label className={cn("flex flex-col gap-1.5 text-sm", disabled && "opacity-50")}>
      <span className="flex items-center justify-between gap-3">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums text-xs text-muted-foreground">{display}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-1.5 w-full accent-primary"
      />
    </label>
  );
}

export function TtsTuning({
  value,
  onChange,
  supportsEmotion,
}: {
  value: TtsTuningValue;
  onChange: (value: TtsTuningValue) => void;
  supportsEmotion: boolean;
}) {
  const tx = useTx();
  const update = (patch: Partial<TtsTuningValue>) => onChange({ ...value, ...patch });
  const linked = tuningAt(value.expressiveness);
  const presetLabel = (preset: TtsPreset) =>
    tx(TTS_PRESETS.find((item) => item.id === preset)?.label ?? "自然");

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-3">
      <Switch
        label={tx("高级参数")}
        hint={tx("展开语速、语气强度和节奏；关闭时使用服务默认值。")}
        checked={value.advanced}
        onChange={(advanced) => update({ advanced })}
      />

      {value.advanced && (
        <div className="flex flex-col gap-3 border-t border-border pt-3">
          {supportsEmotion && (
            <>
              <Switch
                label={tx("相关调节")}
                hint={tx("开启后用一个表达强度滑杆同时调节语速、语气和节奏。")}
                checked={value.linked}
                onChange={(linkedValue) => update({ linked: linkedValue })}
              />
              <div className="flex flex-wrap gap-1.5">
                {TTS_PRESETS.map((preset) => {
                  const active = value.linked && linked.preset === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => onChange(tuningFromPreset(preset.id, value))}
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-xs transition-colors",
                        active
                          ? "border-primary bg-primary/10 text-foreground"
                          : "border-border text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {tx(preset.label)}
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {value.linked && supportsEmotion ? (
            <Range
              label={tx("表达强度")}
              value={value.expressiveness}
              min={0}
              max={1}
              step={0.01}
              display={`${presetLabel(linked.preset)} · ${Math.round(value.expressiveness * 100)}%`}
              onChange={(expressiveness) => update({ expressiveness })}
            />
          ) : (
            <>
              <Range
                label={tx("语速")}
                value={value.speed}
                min={0.8}
                max={1.2}
                step={0.01}
                display={value.speed.toFixed(2)}
                onChange={(speed) => update({ speed })}
              />
              {supportsEmotion && (
                <>
                  <Range
                    label={tx("语气强度")}
                    value={value.exaggeration}
                    min={0.2}
                    max={1}
                    step={0.01}
                    display={value.exaggeration.toFixed(2)}
                    onChange={(exaggeration) => update({ exaggeration })}
                  />
                  <Range
                    label={tx("节奏")}
                    value={value.cfgWeight}
                    min={0.3}
                    max={0.7}
                    step={0.01}
                    display={value.cfgWeight.toFixed(2)}
                    onChange={(cfgWeight) => update({ cfgWeight })}
                  />
                </>
              )}
            </>
          )}

          {!supportsEmotion && (
            <p className="text-xs text-muted-foreground">
              {tx("当前模型只支持语速；语气和节奏请使用多语言或标准模型。")}
            </p>
          )}

          <button
            type="button"
            onClick={() => onChange({ ...DEFAULT_TTS_TUNING })}
            className="flex w-fit items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3.5" />
            {tx("恢复默认")}
          </button>
        </div>
      )}
    </div>
  );
}

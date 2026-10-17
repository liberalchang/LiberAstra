import { Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

interface NumberStepperProps {
  value: number;
  onChange: (n: number) => void;
  min?: number;
  max?: number;
  step?: number;
  ariaLabel?: string;
}

/** 数字步进器：− / + 微调（自动钳位），中间可直接键入，失焦或回车才校验提交。
 *  step 为小数时按小数模式工作（不取整，允许输入小数点）。 */
export function NumberStepper({ value, onChange, min, max, step = 1, ariaLabel }: NumberStepperProps) {
  const isFloat = step % 1 !== 0;
  const decimals = isFloat ? Math.max(1, String(step).split(".")[1]?.length ?? 1) : 0;
  const clamp = (n: number) => {
    const clamped = Math.min(max ?? Number.POSITIVE_INFINITY, Math.max(min ?? Number.NEGATIVE_INFINITY, n));
    return isFloat ? Number(clamped.toFixed(decimals)) : Math.round(clamped);
  };

  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setDraft(String(value));
  }, [value, focused]);

  const commit = () => {
    const n = Number(draft);
    if (draft.trim() && Number.isFinite(n)) onChange(clamp(n));
    else setDraft(String(value));
  };

  const atMin = min != null && value <= min;
  const atMax = max != null && value >= max;
  const bump = (dir: 1 | -1) => () => onChange(clamp(value + dir * step));

  const btnClass = cn(
    "grid w-9 shrink-0 place-items-center text-muted-foreground transition-colors",
    "hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-35",
  );

  return (
    <div className="flex h-11 items-stretch overflow-hidden rounded-[10px] border border-border bg-field focus-within:ring-2 focus-within:ring-ring">
      <button type="button" aria-label="减少" className={btnClass} disabled={atMin} onClick={bump(-1)}>
        <Minus className="size-4" />
      </button>
      <input
        type="text"
        inputMode={isFloat ? "decimal" : "numeric"}
        aria-label={ariaLabel}
        value={draft}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          commit();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        onChange={(e) => {
          if ((isFloat ? /^-?\d*\.?\d*$/ : /^-?\d*$/).test(e.target.value)) setDraft(e.target.value);
        }}
        className="w-full min-w-0 flex-1 bg-transparent text-center text-sm text-foreground focus-visible:outline-none"
      />
      <button type="button" aria-label="增加" className={btnClass} disabled={atMax} onClick={bump(1)}>
        <Plus className="size-4" />
      </button>
    </div>
  );
}

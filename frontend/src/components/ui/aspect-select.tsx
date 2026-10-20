import { Check, ChevronDown, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { useTx } from "@/i18n/tx";

export interface AspectOption {
  ratio: string;
  width: number;
  height: number;
}

/** 自定义宽高比的 ratio 标记。 */
export const CUSTOM_RATIO = "自定义";

const MIN_SIDE = 64;
const MAX_SIDE = 4096;

const clampSide = (n: number) =>
  Math.min(MAX_SIDE, Math.max(MIN_SIDE, Math.round(n) || MIN_SIDE));

/** 自定义边长输入：编辑时只改本地草稿（可清空重输），失焦或回车才钳位提交，非法输入还原。 */
function SideInput({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number;
  onCommit: (n: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setDraft(String(value));
  }, [value, focused]);

  const commit = () => {
    const n = Number(draft);
    if (draft.trim() && Number.isFinite(n) && n > 0) onCommit(clampSide(n));
    else setDraft(String(value));
  };

  return (
    <input
      type="text"
      inputMode="numeric"
      aria-label={label}
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
        if (/^\d*$/.test(e.target.value)) setDraft(e.target.value);
      }}
      className="h-9 w-full min-w-0 rounded-lg border border-border bg-field px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    />
  );
}

/** 文生图可选宽高比（标签 + 像素尺寸）。 */
export const ASPECT_OPTIONS: AspectOption[] = [
  { ratio: "1:1", width: 512, height: 512 },
  { ratio: "1:1", width: 1024, height: 1024 },
  { ratio: "3:4", width: 768, height: 1024 },
  { ratio: "2:3", width: 832, height: 1216 },
  { ratio: "9:16", width: 576, height: 1024 },
  { ratio: "4:3", width: 1024, height: 768 },
  { ratio: "16:9", width: 1024, height: 576 },
];

/** 小方块预览：按真实宽高比伸缩。 */
function RatioGlyph({ width, height, active }: { width: number; height: number; active?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-3.5 rounded-[3px] border-2",
        active ? "border-primary" : "border-muted-foreground/60",
      )}
      style={{ aspectRatio: `${width} / ${height}` }}
    />
  );
}

interface AspectSelectProps {
  label?: string;
  value: AspectOption;
  onChange: (option: AspectOption) => void;
  /** 不传用内置文生图比例表；视频包等场景按包默认长边缩放后传入 */
  options?: AspectOption[];
}

/** 宽高比下拉：标签在左、当前值在右，展开为选项列表（参考 piax 创作间的行式控件）。支持自定义宽高。 */
export function AspectSelect({ label = "宽高比", value, onChange, options }: AspectSelectProps) {
  const tx = useTx();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const ratioOptions = options ?? ASPECT_OPTIONS;

  const isCustom =
    value.ratio === CUSTOM_RATIO ||
    !ratioOptions.some((o) => o.width === value.width && o.height === value.height);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const isSelected = (o: AspectOption) =>
    !isCustom && o.width === value.width && o.height === value.height;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex h-14 w-full items-center justify-between rounded-[10px] border border-border bg-field px-4 text-sm",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          open && "ring-2 ring-ring",
        )}
      >
        <span className="font-medium text-foreground">{tx(label)}</span>
        <span className="flex items-center gap-2.5">
          <RatioGlyph width={value.width} height={value.height} active />
          <span className="font-semibold text-foreground">{tx(value.ratio)}</span>
          <span className="text-muted-foreground">
            {value.width}×{value.height}
          </span>
          <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
        </span>
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute z-30 mt-2 w-full overflow-hidden rounded-[10px] border border-border bg-card shadow-lg"
        >
          {ratioOptions.map((o) => {
            const selected = isSelected(o);
            return (
              <button
                key={`${o.ratio}-${o.width}`}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => {
                  onChange(o);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-3 px-4 py-3 text-sm transition-colors",
                  selected ? "bg-muted" : "hover:bg-muted/60",
                )}
              >
                <RatioGlyph width={o.width} height={o.height} active={selected} />
                <span className="font-semibold text-foreground">{tx(o.ratio)}</span>
                <span className="text-muted-foreground">
                  {o.width}×{o.height}
                </span>
                {selected && <Check className="ml-auto size-4 text-primary" />}
              </button>
            );
          })}

          <div className={cn("border-t border-border", isCustom && "bg-muted")}>
            <button
              type="button"
              role="option"
              aria-selected={isCustom}
              onClick={() => {
                if (!isCustom) onChange({ ratio: CUSTOM_RATIO, width: value.width, height: value.height });
              }}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-3 text-sm transition-colors",
                !isCustom && "hover:bg-muted/60",
              )}
            >
              <SlidersHorizontal className={cn("size-3.5", isCustom ? "text-primary" : "text-muted-foreground/60")} />
              <span className="font-semibold text-foreground">{tx(CUSTOM_RATIO)}</span>
              {isCustom && (
                <span className="text-muted-foreground">
                  {value.width}×{value.height}
                </span>
              )}
              {isCustom && <Check className="ml-auto size-4 text-primary" />}
            </button>
            {isCustom && (
              <div className="flex items-center gap-2 px-4 pb-3">
                <SideInput
                  label={tx("自定义宽度")}
                  value={value.width}
                  onCommit={(n) => onChange({ ...value, ratio: CUSTOM_RATIO, width: n })}
                />
                <span className="shrink-0 text-muted-foreground">×</span>
                <SideInput
                  label={tx("自定义高度")}
                  value={value.height}
                  onCommit={(n) => onChange({ ...value, ratio: CUSTOM_RATIO, height: n })}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

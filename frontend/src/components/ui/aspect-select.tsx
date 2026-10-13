import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface AspectOption {
  ratio: string;
  width: number;
  height: number;
}

/** 文生图可选宽高比（标签 + 像素尺寸）。 */
export const ASPECT_OPTIONS: AspectOption[] = [
  { ratio: "1:1", width: 512, height: 512 },
  { ratio: "1:1", width: 1024, height: 1024 },
  { ratio: "3:4", width: 768, height: 1024 },
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
}

/** 宽高比下拉：标签在左、当前值在右，展开为选项列表（参考 piax 创作间的行式控件）。 */
export function AspectSelect({ label = "宽高比", value, onChange }: AspectSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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

  const isSelected = (o: AspectOption) => o.width === value.width && o.height === value.height;

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
        <span className="font-medium text-foreground">{label}</span>
        <span className="flex items-center gap-2.5">
          <RatioGlyph width={value.width} height={value.height} active />
          <span className="font-semibold text-foreground">{value.ratio}</span>
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
          {ASPECT_OPTIONS.map((o) => {
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
                <span className="font-semibold text-foreground">{o.ratio}</span>
                <span className="text-muted-foreground">
                  {o.width}×{o.height}
                </span>
                {selected && <Check className="ml-auto size-4 text-primary" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { Lightbulb } from "lucide-react";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { SearchSelect, type SearchOption } from "@/components/ui/search-select";
import { cn } from "@/lib/utils";
import { useTx } from "@/i18n/tx";
import type { WorkflowPackOut } from "@/api/client";

/** 工作流包下拉框右侧的「提示」：弹出 manifest 里的 description。 */
function HintButton({ name, description }: { name?: string; description?: string }) {
  const tx = useTx();
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = anchorRef.current;
      const panel = panelRef.current;
      if (!anchor || !panel) return;
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(360, window.innerWidth - 16);
      let left = rect.right - width;
      if (left < 8) left = 8;
      const height = panel.offsetHeight;
      let top = rect.bottom + 6;
      if (top + height > window.innerHeight - 8) {
        top = Math.max(8, rect.top - height - 6);
      }
      setPos((prev) =>
        prev && prev.top === top && prev.left === left && prev.width === width
          ? prev
          : { top, left, width },
      );
    };
    place();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointer = (e: MouseEvent) => {
      const target = e.target as Node;
      if (anchorRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open, name, description]);

  const text = description?.trim();

  return (
    <div ref={anchorRef} className="shrink-0">
      <Button
        type="button"
        variant="outline"
        size="icon"
        className={cn("size-11 rounded-[10px]", open && "text-primary")}
        disabled={!name}
        aria-expanded={open}
        aria-label={tx("查看当前工作流包的用途和用法")}
        title={tx("查看当前工作流包的用途和用法")}
        onClick={() => setOpen((v) => !v)}
      >
        <Lightbulb />
      </Button>
      {open &&
        name &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label={tx("工作流包说明")}
            className="fixed z-50 rounded-xl border border-border bg-card p-3 text-sm shadow-lg"
            style={
              pos
                ? { top: pos.top, left: pos.left, width: pos.width }
                : { top: -9999, left: 8, width: Math.min(360, window.innerWidth - 16) }
            }
          >
            <div className="mb-1.5 font-medium text-foreground">{name}</div>
            <p className="max-h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed text-muted-foreground">
              {text ? tx(text) : tx("这个工作流包没有填写描述。")}
            </p>
          </div>,
          document.body,
        )}
    </div>
  );
}

/** 下拉框占满剩余宽度，「提示」贴在右侧。 */
export function WorkflowPackControl({
  name,
  description,
  children,
}: {
  name?: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="min-w-0 flex-1">{children}</div>
      <HintButton name={name} description={description} />
    </div>
  );
}

const PACK_CAPABILITY: Record<string, string> = {
  t2i: "文生图",
  i2i: "图生图",
  upscale: "修复放大",
  i2v: "图生视频",
  t2v: "文生视频",
  avatar: "数字人",
  motion: "动作迁移",
  tts: "语音",
  analysis: "分析",
};

/** 能力中文名在前，包 id 作为次要信息。 */
export function PackSelect({
  packs,
  value,
  onChange,
  ariaLabel,
}: {
  packs: WorkflowPackOut[] | undefined;
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
}) {
  const tx = useTx();
  const options: SearchOption[] = (packs ?? []).map((pack) => {
    const capability = PACK_CAPABILITY[pack.capability] ?? pack.capability;
    // 只认「官方版 / 越狱版」和包名里的 uncensored。正文里的「官方推荐」「可换越狱」不算版本。
    const text = `${pack.name} ${pack.description}`;
    const edition = /越狱版|uncensored/i.test(text) ? tx("越狱版") : /官方版/.test(text) ? tx("官方版") : "";
    const first = pack.description.split("\n")[0]?.trim() ?? "";
    const short = !edition && first && first.length <= 24 && first !== pack.name ? first : "";
    const detail = edition || short;
    return {
      value: pack.name,
      label: detail ? `${tx(capability)} · ${detail}` : tx(capability) || pack.name,
      hint: pack.name,
    };
  });
  if (value && !options.some((item) => item.value === value)) {
    options.unshift({ value, label: value, hint: value });
  }
  return (
    <SearchSelect
      ariaLabel={ariaLabel}
      value={value}
      onChange={onChange}
      options={options}
      placeholder={tx("搜索工作流包")}
      emptyText={tx("没有匹配项")}
    />
  );
}

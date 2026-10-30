import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { useTx } from "@/i18n/tx";

interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
  /** 左栏宽度比例（0.28–0.72 之间拖动），按 storageKey 持久化 */
  storageKey: string;
  defaultRatio?: number;
  /** 固定在左栏底部，不随表单滚走 */
  footer?: ReactNode;
}

/** 左右分栏，分割线支持拖动；小屏自动堆叠为上下布局。 */
export function SplitPane({ left, right, storageKey, defaultRatio = 0.46, footer }: SplitPaneProps) {
  const tx = useTx();
  const [ratio, setRatio] = useState(() => {
    try {
      const saved = localStorage.getItem(`liberastra-split:${storageKey}`);
      const parsed = saved ? Number(saved) : Number.NaN;
      return Number.isFinite(parsed) && parsed > 0.2 && parsed < 0.8 ? parsed : defaultRatio;
    } catch {
      return defaultRatio;
    }
  });
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setRatio(Math.min(0.72, Math.max(0.28, (e.clientX - rect.left) / rect.width)));
  };
  const onPointerUp = () => {
    if (!dragging) return;
    setDragging(false);
    try {
      localStorage.setItem(`liberastra-split:${storageKey}`, String(ratio));
    } catch {
      /* 隐私模式 */
    }
  };

  return (
    <div ref={containerRef} className="flex flex-col gap-6 lg:flex-row lg:items-stretch lg:gap-0">
      <div
        className="flex w-full min-w-0 max-h-[calc(100dvh-15rem)] flex-col lg:sticky lg:top-0 lg:w-[var(--lw)] lg:shrink-0 lg:self-start lg:overflow-hidden"
        style={{ "--lw": `${ratio * 100}%` } as React.CSSProperties}
      >
        <div className="min-h-0 flex-1 overflow-y-auto">{left}</div>
        {footer ? <div className="shrink-0 border-t border-border bg-background pt-3">{footer}</div> : null}
      </div>
      {/* 分割手柄：桌面端可拖动 */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={tx("调整左右面板宽度")}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        className={`hidden w-3 shrink-0 cursor-col-resize touch-none select-none items-center justify-center lg:flex ${dragging ? "text-primary" : "text-muted-foreground/50"}`}
      >
        <div className={`h-12 w-1 rounded-full transition-colors ${dragging ? "bg-primary" : "bg-border group-hover:bg-primary"}`} />
      </div>
      <div className="min-w-0 flex-1">{right}</div>
    </div>
  );
}

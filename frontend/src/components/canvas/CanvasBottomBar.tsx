/** 画布底部工具栏（LibTv 风格）：添加节点 / 抓手-选择模式切换 / 整理。
 * 放在 bottom-center 悬浮 pill 里,让「怎么加节点、怎么移动画布」一眼可见。
 */
import { Hand, LayoutGrid, MousePointer2, Plus } from "lucide-react";
import { Panel } from "@xyflow/react";

import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";

export type CanvasTool = "hand" | "select";

export function CanvasBottomBar({
  tool,
  onToolChange,
  onAdd,
  onLayout,
}: {
  tool: CanvasTool;
  onToolChange: (tool: CanvasTool) => void;
  onAdd: () => void;
  onLayout: () => void;
}) {
  const tx = useTx();
  const btn =
    "grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";
  const active = "bg-primary/15 text-primary hover:bg-primary/15 hover:text-primary";
  return (
    <Panel
      position="bottom-center"
      className="flex items-center gap-1 rounded-xl border border-border bg-card/95 p-1 shadow-lg backdrop-blur"
    >
      <button type="button" className={btn} title={tx("添加节点")} onClick={onAdd}>
        <Plus className="size-4" />
      </button>
      <button
        type="button"
        className={cn(btn, tool === "hand" && active)}
        title={tx("抓手：左键拖动移动画布")}
        aria-pressed={tool === "hand"}
        onClick={() => onToolChange("hand")}
      >
        <Hand className="size-4" />
      </button>
      <button
        type="button"
        className={cn(btn, tool === "select" && active)}
        title={tx("选择：左键框选节点（中/右键仍可拖动画布）")}
        aria-pressed={tool === "select"}
        onClick={() => onToolChange("select")}
      >
        <MousePointer2 className="size-4" />
      </button>
      <div className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      <button type="button" className={btn} title={tx("整理画布：按依赖分层自动排列")} onClick={onLayout}>
        <LayoutGrid className="size-4" />
      </button>
    </Panel>
  );
}

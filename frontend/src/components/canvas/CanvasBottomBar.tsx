/** 画布底部工具栏（LibTv 风格）：添加节点 / 抓手-选择模式切换 / 整理 / 撤销重做。
 * 放在 bottom-center 悬浮 pill 里,让「怎么加节点、怎么移动画布」一眼可见。
 */
import { Hand, LayoutGrid, Menu, MousePointer2, Plus, Redo2, Undo2 } from "lucide-react";
import { Panel } from "@xyflow/react";

import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";
import { useCanvasStore } from "@/stores/canvas";

export type CanvasTool = "hand" | "select";

export function CanvasBottomBar({
  tool,
  onToolChange,
  onAdd,
  onMenu,
  onLayout,
}: {
  tool: CanvasTool;
  onToolChange: (tool: CanvasTool) => void;
  onAdd: (anchor: HTMLElement) => void;
  onMenu: () => void;
  onLayout: () => void;
}) {
  const tx = useTx();
  const canUndo = useCanvasStore((s) => s.canUndo);
  const canRedo = useCanvasStore((s) => s.canRedo);
  const undo = useCanvasStore((s) => s.undo);
  const redo = useCanvasStore((s) => s.redo);
  const btn =
    "grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40";
  const active = "bg-primary/15 text-primary hover:bg-primary/15 hover:text-primary";
  return (
    <Panel
      position="bottom-center"
      className="flex items-center gap-1 rounded-xl border border-border bg-card/95 p-1 shadow-lg backdrop-blur"
    >
      <button type="button" className={btn} title={tx("撤销 (Ctrl+Z)")} aria-label={tx("撤销")} disabled={!canUndo} onClick={undo}>
        <Undo2 className="size-4" />
      </button>
      <button type="button" className={btn} title={tx("重做 (Ctrl+Shift+Z)")} aria-label={tx("重做")} disabled={!canRedo} onClick={redo}>
        <Redo2 className="size-4" />
      </button>
      <div className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      <button type="button" className={btn} title={tx("功能菜单")} aria-label={tx("功能菜单")} onClick={onMenu}>
        <Menu className="size-4" />
      </button>
      <button type="button" className={btn} title={tx("添加节点")} aria-label={tx("添加节点")} onClick={(event) => onAdd(event.currentTarget)}>
        <Plus className="size-4" />
      </button>
      <button
        type="button"
        className={cn(btn, tool === "hand" && active)}
        title={tx("抓手：左键拖动移动画布")}
        aria-label={tx("抓手模式")}
        aria-pressed={tool === "hand"}
        onClick={() => onToolChange("hand")}
      >
        <Hand className="size-4" />
      </button>
      <button
        type="button"
        className={cn(btn, tool === "select" && active)}
        title={tx("选择：左键框选节点（中/右键仍可拖动画布）")}
        aria-label={tx("选择模式")}
        aria-pressed={tool === "select"}
        onClick={() => onToolChange("select")}
      >
        <MousePointer2 className="size-4" />
      </button>
      <div className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      <button type="button" className={btn} title={tx("整理画布：按依赖分层自动排列")} aria-label={tx("整理画布")} onClick={onLayout}>
        <LayoutGrid className="size-4" />
      </button>
    </Panel>
  );
}

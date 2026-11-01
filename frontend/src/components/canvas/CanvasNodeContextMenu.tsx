/** 节点右键菜单：添加到导演台 / 删除节点。 */
import { Sparkles, Trash2 } from "lucide-react";
import { useEffect } from "react";

import { useTx } from "@/i18n/tx";

export function CanvasNodeContextMenu({
  x,
  y,
  label,
  onAddToDirector,
  onDelete,
  onClose,
}: {
  x: number;
  y: number;
  label: string;
  onAddToDirector: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const tx = useTx();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const item =
    "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors hover:bg-muted";

  return (
    <>
      <button
        type="button"
        className="absolute inset-0 z-40 cursor-default"
        aria-label={tx("关闭节点菜单")}
        onClick={onClose}
      />
      <div
        className="absolute z-50 w-52 rounded-xl border border-border bg-card/95 p-1.5 shadow-2xl backdrop-blur-xl"
        style={{ left: x, top: y }}
        role="menu"
      >
        <div className="flex items-center gap-2 px-2 py-1.5">
          <span className="grid size-6 place-items-center rounded-md bg-primary/10 text-primary">
            <Sparkles className="size-3.5" />
          </span>
          <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
            {label}
          </span>
        </div>
        <div className="my-1 border-t border-border/70" />
        <button type="button" className={item} onClick={onAddToDirector}>
          <Sparkles className="size-3.5 text-primary" />
          {tx("添加到导演台")}
        </button>
        <button
          type="button"
          className={`${item} text-danger hover:bg-danger/10`}
          onClick={onDelete}
        >
          <Trash2 className="size-3.5" />
          {tx("删除节点")}
          <span className="ml-auto text-[10px] text-muted-foreground">Del</span>
        </button>
      </div>
    </>
  );
}

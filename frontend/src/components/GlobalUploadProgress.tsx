import { Loader2 } from "lucide-react";
import { useSyncExternalStore } from "react";

import { getUploads, subscribeUploads } from "@/lib/uploadProgress";
import { useTx } from "@/i18n/tx";

export function GlobalUploadProgress() {
  const tx = useTx();
  const tasks = useSyncExternalStore(subscribeUploads, getUploads, getUploads);
  if (tasks.length === 0) return null;
  const visible = tasks.slice(-3);
  return (
    <div className="fixed bottom-4 right-4 z-[80] flex w-72 flex-col gap-2 rounded-xl border border-border bg-card p-3 shadow-xl">
      {visible.map((task) => (
        <div key={task.id} className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-xs">
            <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" />
            <span className="min-w-0 flex-1 truncate" title={task.label}>
              {tx("上传中…")} {task.label}
            </span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {Math.round(task.percent)}%
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-150"
              style={{ width: `${task.percent}%` }}
            />
          </div>
        </div>
      ))}
      {tasks.length > visible.length && (
        <p className="text-[10px] text-muted-foreground">+{tasks.length - visible.length}</p>
      )}
    </div>
  );
}

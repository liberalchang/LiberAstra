/** 功能页主生成按钮：运行中再次点击会弹出中断确认。 */
import { Square } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { useTx } from "@/i18n/tx";

export function GenerateButton({
  running,
  jobId,
  progress,
  disabled = false,
  onGenerate,
  label,
  className,
}: {
  running: boolean;
  jobId?: string | null;
  progress?: number;
  disabled?: boolean;
  onGenerate: () => void;
  label: string;
  className?: string;
}) {
  const tx = useTx();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancel = async () => {
    if (!jobId) return;
    setCanceling(true);
    setError(null);
    try {
      await api.cancelJob(jobId);
      setConfirmOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : tx("中断失败"));
    } finally {
      setCanceling(false);
    }
  };

  return (
    <>
      <Button
        className={className}
        disabled={running ? !jobId : disabled}
        title={running ? tx("点击中断当前任务") : undefined}
        onClick={() => {
          if (!running) {
            onGenerate();
            return;
          }
          setError(null);
          setConfirmOpen(true);
        }}
      >
        {running ? (
          <>
            <Square className="size-3.5 fill-current" />
            {tx("生成中… {pct}%（点击中断）", {
              pct: Math.round((progress ?? 0) * 100),
            })}
          </>
        ) : (
          label
        )}
      </Button>
      {confirmOpen && (
        <ConfirmDialog
          title={tx("中断当前任务？")}
          message={tx("后端会取消这个任务，并向 ComfyUI 发送中断请求。已经完成的结果会保留。")}
          confirmLabel={tx("中断任务")}
          closeLabel={tx("继续生成")}
          danger
          busy={canceling}
          error={error}
          onConfirm={() => void cancel()}
          onClose={() => setConfirmOpen(false)}
        />
      )}
    </>
  );
}

/** 通用确认弹窗：危险操作用红色主按钮，支持 busy / error。 */
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { useTx } from "@/i18n/tx";

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
  busy = false,
  error,
  danger = false,
  closeLabel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
  error?: string | null;
  danger?: boolean;
  closeLabel?: string;
}) {
  const tx = useTx();
  return (
    <LightboxShell
      onClose={busy ? () => undefined : onClose}
      ariaLabel={title}
      className="max-w-md"
    >
      <div className="flex flex-col gap-4 p-5">
        <h2 className="text-base font-medium">{title}</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            {closeLabel ?? tx("取消")}
          </Button>
          <Button
            className={danger ? "bg-danger text-white hover:bg-danger/90" : undefined}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy && <Loader2 className="size-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </div>
      </div>
    </LightboxShell>
  );
}

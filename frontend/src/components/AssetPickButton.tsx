/** 上传区下方的「从资源库选择」按钮：打开选择器并回传选中的资产。 */
import { Images, Loader2 } from "lucide-react";
import { useState } from "react";

import type { AssetOut } from "@/api/client";
import { AssetPicker, type AssetKind } from "@/components/AssetPicker";
import { Button } from "@/components/ui/button";
import { useTx } from "@/i18n/tx";

export function AssetPickButton({
  kind,
  multiple = false,
  onPick,
  disabled = false,
  label,
}: {
  kind: AssetKind | AssetKind[];
  multiple?: boolean;
  onPick: (assets: AssetOut[]) => void | Promise<void>;
  disabled?: boolean;
  label?: string;
}) {
  const tx = useTx();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const pick = async (assets: AssetOut[]) => {
    setOpen(false);
    setBusy(true);
    try {
      await onPick(assets);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-2"
        disabled={disabled || busy}
        onClick={() => setOpen(true)}
      >
        {busy ? <Loader2 className="animate-spin" /> : <Images />}
        {busy ? tx("加载中…") : tx(label ?? "从资源库选择")}
      </Button>
      {open && (
        <AssetPicker
          kind={kind}
          multiple={multiple}
          onPick={(assets) => void pick(assets)}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

/** 资源库选择器：按类型列出资产,点击选择（画布输入节点用）。 */
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { api, type AssetOut } from "@/api/client";
import { MediaThumb } from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { useTx } from "@/i18n/tx";

export function AssetPicker({
  kind,
  onPick,
  onClose,
}: {
  kind: "image" | "video" | "audio";
  onPick: (asset: AssetOut) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const { data, isLoading } = useQuery({
    queryKey: ["assets", kind],
    queryFn: () => api.listAssets(kind),
  });

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="flex max-h-[70vh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-card shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="text-sm font-medium">{tx("从资源库选择")}</h3>
          <Button variant="ghost" size="icon" className="size-7" onClick={onClose} aria-label={tx("关闭")}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="grid flex-1 grid-cols-3 gap-2 overflow-y-auto p-4 sm:grid-cols-4">
          {isLoading && <p className="col-span-full text-sm text-muted-foreground">{tx("加载中…")}</p>}
          {!isLoading && !data?.length && (
            <p className="col-span-full text-sm text-muted-foreground">{tx("资源库暂无该类型文件")}</p>
          )}
          {data?.map((asset) => (
            <button
              key={asset.id}
              type="button"
              className="overflow-hidden rounded-lg border border-border transition hover:border-primary"
              onClick={() => onPick(asset)}
            >
              <MediaThumb assetId={asset.id} kind={asset.kind} className="aspect-video w-full object-cover" />
              <span className="block truncate px-1.5 py-1 text-[10px] text-muted-foreground">
                #{asset.id} {String(asset.meta?.source_name ?? asset.path)}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** 资源库选择器：按媒体类型列出资产，支持单选或多选。 */
import { useQuery } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { api, type AssetOut } from "@/api/client";
import { MediaThumb } from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { useTx } from "@/i18n/tx";

export type AssetKind = "image" | "video" | "audio";

const KIND_LABEL: Record<AssetKind, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
};

function assetName(asset: AssetOut): string {
  return String(asset.meta?.source_name ?? asset.path.split("/").pop() ?? `#${asset.id}`);
}

export function AssetPicker({
  kind,
  multiple = false,
  onPick,
  onClose,
}: {
  kind: AssetKind | AssetKind[];
  multiple?: boolean;
  onPick: (assets: AssetOut[]) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const kinds = useMemo(() => (Array.isArray(kind) ? kind : [kind]), [kind]);
  const [selected, setSelected] = useState<AssetOut[]>([]);
  const { data, isLoading } = useQuery({
    queryKey: ["assets", "picker", kinds.join(",")],
    queryFn: () => (kinds.length === 1 ? api.listAssets(kinds[0]) : api.listAssets()),
  });
  const assets = (data ?? []).filter((asset) => kinds.includes(asset.kind as AssetKind));

  const toggle = (asset: AssetOut) => {
    if (!multiple) {
      onPick([asset]);
      return;
    }
    setSelected((current) =>
      current.some((item) => item.id === asset.id)
        ? current.filter((item) => item.id !== asset.id)
        : [...current, asset],
    );
  };

  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="flex max-h-[80vh] w-full max-w-3xl flex-col rounded-2xl border border-border bg-card shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="text-sm font-medium">
            {tx("从资源库选择")}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {kinds.map((item) => tx(KIND_LABEL[item])).join(" / ")}
            </span>
          </h3>
          <Button variant="ghost" size="icon" className="size-7" onClick={onClose} aria-label={tx("关闭")}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-2 gap-2 overflow-y-auto p-4 sm:grid-cols-3 md:grid-cols-4">
          {isLoading && <p className="col-span-full text-sm text-muted-foreground">{tx("加载中…")}</p>}
          {!isLoading && assets.length === 0 && (
            <p className="col-span-full text-sm text-muted-foreground">{tx("资源库暂无该类型文件")}</p>
          )}
          {assets.map((asset) => {
            const picked = selected.some((item) => item.id === asset.id);
            return (
              <button
                key={asset.id}
                type="button"
                className={`relative flex h-28 flex-col overflow-hidden rounded-lg border text-left transition ${
                  picked ? "border-primary ring-1 ring-primary" : "border-border hover:border-primary/60"
                }`}
                onClick={() => toggle(asset)}
              >
                <MediaThumb assetId={asset.id} kind={asset.kind} className="h-20 w-full shrink-0" />
                <span className="block w-full truncate px-1.5 py-1 text-[10px] text-muted-foreground">
                  #{asset.id} {assetName(asset)}
                </span>
                {picked && (
                  <span className="absolute right-1.5 top-1.5 grid size-5 place-items-center rounded-full bg-primary text-primary-foreground">
                    <Check className="size-3" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {multiple && (
          <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
            <span className="mr-auto text-xs text-muted-foreground">
              {tx("已选 {n} 项", { n: selected.length })}
            </span>
            <Button variant="outline" onClick={onClose}>
              {tx("取消")}
            </Button>
            <Button disabled={selected.length === 0} onClick={() => onPick(selected)}>
              {tx("确认选择")}
            </Button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

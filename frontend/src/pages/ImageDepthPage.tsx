/** 图像 → 深度图生成：通过已启用的 liber_depth 批量转换。 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Layers, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, fetchAssetBlob, type AssetOut } from "@/api/client";
import { MediaLightbox, MediaThumb, type PreviewTarget } from "@/components/MediaLightbox";
import { PageHeader } from "@/components/PageShell";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { SplitPane } from "@/components/ui/split-pane";
import { useTx } from "@/i18n/tx";

const DEFAULT_MODEL = "dpt_swin2_large_384";

function sourceName(asset: AssetOut): string {
  const name = asset.meta?.source_name;
  return typeof name === "string" && name ? name : "depth.png";
}

async function downloadAsset(asset: AssetOut) {
  const blob = await fetchAssetBlob(asset.id);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = sourceName(asset);
  link.click();
  URL.revokeObjectURL(url);
}

export function ImageDepthPage() {
  const tx = useTx();
  const [providerId, setProviderId] = useState<number | "">("");
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [device, setDevice] = useState("cuda");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [batch, setBatch] = useState<AssetOut[]>([]);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);

  const fileKey = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;
  const addFiles = (list: FileList | null) => {
    if (!list?.length) return;
    const incoming = Array.from(list);
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey));
      const next = [...prev];
      for (const file of incoming) {
        const key = fileKey(file);
        if (!seen.has(key)) {
          seen.add(key);
          next.push(file);
        }
      }
      return next;
    });
  };
  const removeFile = (index: number) => setFiles((prev) => prev.filter((_, item) => item !== index));
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const providers = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const history = useQuery({
    queryKey: ["assets", "image"],
    queryFn: () => api.listAssets("image"),
  });
  const depthProviders = useMemo(
    () => (providers.data ?? []).filter((item) => item.type === "liber_depth" && item.enabled),
    [providers.data],
  );
  const selected = depthProviders.find((item) => item.id === providerId) ?? depthProviders[0];
  const modelOptions = useMemo(() => {
    const ids = selected?.models?.filter(Boolean) ?? [];
    if (ids.length === 0) return [DEFAULT_MODEL];
    return ids.includes(DEFAULT_MODEL) ? [DEFAULT_MODEL, ...ids.filter((id) => id !== DEFAULT_MODEL)] : ids;
  }, [selected]);
  useEffect(() => {
    if (!modelOptions.includes(model)) setModel(modelOptions[0] ?? DEFAULT_MODEL);
  }, [model, modelOptions]);
  const past = (history.data ?? []).filter((asset) => asset.meta?.op === "depth");

  const convert = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      if (selected) form.set("provider_id", String(selected.id));
      form.set("model", model);
      form.set("device", device);
      for (const file of files) form.append("images", file);
      return api.convertDepth(form);
    },
    onSuccess: (assets) => {
      setError(null);
      setBatch(assets);
      setFiles([]);
      void history.refetch();
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="image"
        icon={Layers}
        title={tx("深度图生成")}
        description={tx("一次转换多张图片，文件名会变成原名加 _depth.png。越亮表示离镜头越近。")}
      />
      <SplitPane
        storageKey="image-depth"
        left={
          <Card>
            <CardContent className="flex flex-col gap-4 pt-5">
              {depthProviders.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {tx("没有已启用的深度服务。请到资源 → 插件启用，或在服务提供方添加 Liber Depth。")}
                </p>
              ) : (
                <>
                  <Field label={tx("深度图服务")} hint={tx("选择已启用的 Liber Depth。本机插件启用后会自动出现在这里。")}>
                    <select
                      className={selectClass}
                      value={selected?.id ?? ""}
                      onChange={(event) => setProviderId(Number(event.target.value))}
                    >
                      {depthProviders.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label={tx("深度模型")}>
                      <select className={selectClass} value={model} onChange={(event) => setModel(event.target.value)}>
                        {modelOptions.map((id) => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={tx("硬件加速")}>
                      <select className={selectClass} value={device} onChange={(event) => setDevice(event.target.value)}>
                        <option value="cuda">cuda</option>
                        <option value="cpu">cpu</option>
                      </select>
                    </Field>
                  </div>
                </>
              )}
              <Field
                label={tx("待转换图片")}
                hint={tx("可多选、可分多次添加，也可以直接拖拽。传错了在下方缩略图上删除。")}
              >
                <FileDrop
                  accept="image/*"
                  multiple
                  clearAfterSelect
                  title={tx("点击或拖拽上传图片")}
                  subtitle={tx("支持多选、多次添加")}
                  onSelect={addFiles}
                />
                {files.length > 0 && (
                  <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                    {files.map((file, index) => (
                      <div
                        key={fileKey(file)}
                        className="group relative size-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted"
                      >
                        <img src={previews[index]} alt={file.name} className="size-full object-cover" />
                        <button
                          type="button"
                          onClick={() => removeFile(index)}
                          title={tx("移除 {name}", { name: file.name })}
                          className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-danger group-hover:opacity-100"
                        >
                          <X className="size-3" />
                        </button>
                        <span className="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-[10px] leading-none text-white">
                          {file.name}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Field>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button
                className={submitButtonClass}
                disabled={!selected || files.length === 0 || convert.isPending}
                onClick={() => convert.mutate()}
              >
                {convert.isPending ? tx("转换中…") : tx("开始转换")}
              </Button>
            </CardContent>
          </Card>
        }
        right={
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">{tx("本批结果")}</h2>
              {batch.length > 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void Promise.all(batch.map((asset) => downloadAsset(asset)))}
                >
                  <Download className="size-4" />
                  {tx("批量下载")}
                </Button>
              )}
            </div>
            {batch.length === 0 ? (
              <p className="text-sm text-muted-foreground">{tx("还没有结果。")}</p>
            ) : (
              <ResultGrid assets={batch} onOpen={setPreview} />
            )}
            <h2 className="text-sm font-medium">{tx("历史深度图")}</h2>
            <ResultGrid assets={past} onOpen={setPreview} />
          </div>
        }
      />
      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

function ResultGrid({
  assets,
  onOpen,
}: {
  assets: AssetOut[];
  onOpen: (target: PreviewTarget) => void;
}) {
  const tx = useTx();
  if (assets.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {assets.map((asset) => (
        <button
          key={asset.id}
          type="button"
          className="overflow-hidden rounded-xl border border-border text-left"
          onClick={() =>
            onOpen({
              id: asset.id,
              kind: "image",
              name: sourceName(asset),
              size: asset.size,
              createdAt: asset.created_at,
              meta: asset.meta,
            })
          }
        >
          <MediaThumb assetId={asset.id} kind="image" className="aspect-square w-full object-cover" />
          <div className="flex items-center gap-2 px-2 py-1.5">
            <span className="min-w-0 flex-1 truncate text-xs">{sourceName(asset)}</span>
            <span
              className="text-muted-foreground"
              onClick={(event) => {
                event.stopPropagation();
                void downloadAsset(asset);
              }}
            >
              <Download className="size-3.5" aria-label={tx("下载")} />
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

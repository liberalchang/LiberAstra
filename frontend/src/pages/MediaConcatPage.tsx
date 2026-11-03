import { ArrowDown, ArrowUp, Images, Loader2, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, TERMINAL_STATUSES, type AssetOut } from "@/api/client";
import { MediaThumb } from "@/components/MediaLightbox";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileDrop } from "@/components/ui/file-drop";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { useTrackedJob } from "@/hooks/useJob";
import { useTx } from "@/i18n/tx";

type Kind = "image" | "video" | "audio";

const META: Record<Kind, { title: string; description: string; accept: string; min: number }> = {
  image: {
    title: "图片拼接",
    description: "上传或选择多张图片，按顺序横排、竖排或网格拼成一张。",
    accept: "image/*",
    min: 2,
  },
  video: {
    title: "视频拼接",
    description: "上传或选择多段视频，按顺序拼成一段。",
    accept: "video/*",
    min: 1,
  },
  audio: {
    title: "音频拼接",
    description: "上传或选择多段音频，按顺序拼成一段。",
    accept: "audio/*",
    min: 1,
  },
};

export function MediaConcatPage({ kind }: { kind: Kind }) {
  const tx = useTx();
  const queryClient = useQueryClient();
  const meta = META[kind];
  const { job, setJobId } = useTrackedJob(`tool-${kind}-concat`);
  const [selected, setSelected] = useState<AssetOut[]>([]);
  const [layout, setLayout] = useState<"horizontal" | "vertical" | "grid">("horizontal");
  const [columns, setColumns] = useState(2);
  const [gap, setGap] = useState(4);
  const [gapColor, setGapColor] = useState("#FFFFFF");
  const [error, setError] = useState<string | null>(null);

  const { data: assets, isLoading } = useQuery({
    queryKey: ["assets", kind, "tool"],
    queryFn: () => api.listAssets(kind),
  });

  const upload = useMutation({
    mutationFn: async (files: FileList | null) => {
      for (const file of Array.from(files ?? [])) {
        await api.uploadFileAsAsset(file, kind);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["assets", kind, "tool"] });
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const submit = useMutation({
    mutationFn: () =>
      api.submitToolConcat({
        kind,
        asset_ids: selected.map((asset) => asset.id),
        layout,
        columns,
        gap,
        gap_color: gapColor,
      }),
    onSuccess: (created) => {
      setJobId(created.id);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const busy = upload.isPending || submit.isPending || (job != null && !TERMINAL_STATUSES.includes(job.status));
  const canSubmit = selected.length >= meta.min && !busy;

  const move = (index: number, delta: number) => {
    setSelected((current) => {
      const next = [...current];
      const target = index + delta;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="clips" icon={Images} title={tx(meta.title)} description={tx(meta.description)} />
      <SplitPane
        storageKey={`tool-${kind}-concat`}
        left={
          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{tx("素材")}</CardTitle>
                <CardDescription>{tx("上传后会进入资源库；也可以直接选已有素材。")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <FileDrop
                  accept={meta.accept}
                  multiple
                  clearAfterSelect
                  title={upload.isPending ? tx("上传中…") : tx("点击或拖拽上传")}
                  subtitle={tx("可多选、多次添加")}
                  onSelect={(files) => upload.mutate(files)}
                />
                {error && <p className="text-sm text-danger">{error}</p>}
                <div className="grid max-h-72 grid-cols-3 gap-2 overflow-y-auto rounded-xl border border-border p-2 sm:grid-cols-4">
                  {isLoading && <p className="col-span-full text-sm text-muted-foreground">{tx("加载中…")}</p>}
                  {!isLoading && !assets?.length && (
                    <p className="col-span-full text-sm text-muted-foreground">{tx("资源库暂无该类型文件")}</p>
                  )}
                  {assets?.map((asset) => {
                    const picked = selected.some((item) => item.id === asset.id);
                    return (
                      <button
                        key={asset.id}
                        type="button"
                        className={`flex h-28 flex-col overflow-hidden rounded-lg border text-left transition ${picked ? "border-primary ring-1 ring-primary" : "border-border hover:border-primary/60"}`}
                        onClick={() =>
                          setSelected((current) =>
                            picked ? current.filter((item) => item.id !== asset.id) : [...current, asset],
                          )
                        }
                      >
                        <MediaThumb assetId={asset.id} kind={asset.kind} className="h-20 w-full shrink-0" />
                        <span className="block truncate px-1.5 py-1 text-[10px] text-muted-foreground">
                          #{asset.id} {String(asset.meta?.source_name ?? asset.path)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{tx("顺序")}</CardTitle>
                <CardDescription>{tx("按此顺序拼接；图片至少 2 张。")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {selected.length === 0 && <p className="text-sm text-muted-foreground">{tx("还没有选择素材")}</p>}
                {selected.map((asset, index) => (
                  <div key={asset.id} className="flex items-center gap-2 rounded-lg border border-border px-2 py-1.5">
                    <span className="w-5 shrink-0 text-xs tabular-nums text-muted-foreground">{index + 1}</span>
                    <MediaThumb assetId={asset.id} kind={asset.kind} className="size-10 rounded-md" />
                    <span className="min-w-0 flex-1 truncate text-sm">#{asset.id}</span>
                    <Button size="icon" variant="ghost" aria-label={tx("上移")} disabled={index === 0} onClick={() => move(index, -1)}>
                      <ArrowUp />
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={tx("下移")} disabled={index === selected.length - 1} onClick={() => move(index, 1)}>
                      <ArrowDown />
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={tx("移除")} onClick={() => setSelected((current) => current.filter((item) => item.id !== asset.id))}>
                      <Trash2 />
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>

            {kind === "image" && (
              <Card>
                <CardHeader>
                  <CardTitle>{tx("布局")}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <Field label={tx("排列")}>
                    <select className={selectClass} value={layout} onChange={(event) => setLayout(event.target.value as typeof layout)}>
                      <option value="horizontal">{tx("横排")}</option>
                      <option value="vertical">{tx("竖排")}</option>
                      <option value="grid">{tx("网格")}</option>
                    </select>
                  </Field>
                  {layout === "grid" && (
                    <Field label={tx("列数")}>
                      <Input type="number" min={1} max={16} value={columns} onChange={(event) => setColumns(Number(event.target.value) || 1)} />
                    </Field>
                  )}
                  <Field label={tx("间隔")}>
                    <Input type="number" min={0} max={256} value={gap} onChange={(event) => setGap(Number(event.target.value) || 0)} />
                  </Field>
                  <Field label={tx("间隔颜色")}>
                    <Input type="color" value={gapColor} onChange={(event) => setGapColor(event.target.value)} />
                  </Field>
                </CardContent>
              </Card>
            )}

            <Button className={submitButtonClass} disabled={!canSubmit} onClick={() => submit.mutate()}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {tx("开始拼接")}
            </Button>
          </div>
        }
        right={<ResultPanel job={job ?? null} mediaKind={kind} historyKind={kind} jobKind="media.concat" emptyHint={tx("拼接结果会出现在这里")} />}
      />
    </div>
  );
}

import { ArrowDown, ArrowUp, Images, Loader2, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, TERMINAL_STATUSES, type AssetOut } from "@/api/client";
import { AssetPickButton } from "@/components/AssetPickButton";
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
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";

type Kind = "image" | "video" | "audio";

function assetLabel(asset: AssetOut): string {
  return String(asset.meta?.source_name ?? asset.path.split("/").pop() ?? `#${asset.id}`);
}

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
  const [storedIds, setStoredIds] = usePersistentState<number[]>(
    `tool-${kind}-concat:asset-ids`,
    [],
  );
  const uploadedIds = useRef<Set<number>>(new Set());
  const hydrated = useRef(false);

  useEffect(() => {
    const ids = storedIds;
    if (ids.length === 0) {
      hydrated.current = true;
      return;
    }
    let alive = true;
    void Promise.allSettled(ids.map((id) => api.getAsset(id))).then((results) => {
      if (!alive) return;
      const assets = results
        .filter(
          (result): result is PromiseFulfilledResult<AssetOut> => result.status === "fulfilled",
        )
        .map((result) => result.value)
        .filter((asset) => asset.kind === kind);
      setSelected((current) => {
        const next = [...current];
        for (const asset of assets) {
          if (!next.some((item) => item.id === asset.id)) next.push(asset);
        }
        return next;
      });
      hydrated.current = true;
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    setStoredIds(selected.map((asset) => asset.id));
  }, [selected, setStoredIds]);

  const mergeAssets = (assets: AssetOut[]) => {
    setSelected((current) => [
      ...current,
      ...assets.filter(
        (asset) => asset.kind === kind && !current.some((item) => item.id === asset.id),
      ),
    ]);
    setError(null);
  };

  const removeAsset = (asset: AssetOut) => {
    setSelected((current) => current.filter((item) => item.id !== asset.id));
    if (!asset.hidden || !uploadedIds.current.has(asset.id)) return;
    uploadedIds.current.delete(asset.id);
    void api.deleteAsset(asset.id).then(
      () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
      () => {},
    );
  };

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const added: AssetOut[] = [];
      for (const file of files) {
        const created = await api.uploadFileAsAsset(file, kind, true);
        added.push(await api.getAsset(created.asset_id));
      }
      return added;
    },
    onSuccess: (added) => {
      for (const asset of added) uploadedIds.current.add(asset.id);
      mergeAssets(added);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
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
      uploadedIds.current.clear();
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
                <CardDescription>{tx("上传后自动加入下方顺序；隐藏资源可在选择器中直接复用。")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <FileDrop
                  accept={meta.accept}
                  multiple
                  clearAfterSelect
                  names={selected.map(assetLabel)}
                  title={upload.isPending ? tx("上传中…") : tx("点击或拖拽上传")}
                  subtitle={tx("可多选、多次添加")}
                  onSelect={(files) => {
                    if (files?.length) upload.mutate(files);
                  }}
                />
                <AssetPickButton
                  kind={kind}
                  multiple
                  onPick={(assets) => mergeAssets(assets)}
                />
                {error && <p className="text-sm text-danger">{error}</p>}
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
                    <span className="min-w-0 flex-1 truncate text-sm">{assetLabel(asset)}</span>
                    <Button size="icon" variant="ghost" aria-label={tx("上移")} disabled={index === 0} onClick={() => move(index, -1)}>
                      <ArrowUp />
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={tx("下移")} disabled={index === selected.length - 1} onClick={() => move(index, 1)}>
                      <ArrowDown />
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={tx("移除")} onClick={() => removeAsset(asset)}>
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
        right={<ResultPanel job={job ?? null} mediaKind={kind} historyKind={kind} jobFunction="media.concat" emptyHint={tx("拼接结果会出现在这里")} />}
      />
    </div>
  );
}

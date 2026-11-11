import { Loader2, Scissors, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

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

function assetLabel(asset: AssetOut): string {
  return String(asset.meta?.source_name ?? asset.path.split("/").pop() ?? `#${asset.id}`);
}

export function AudioExtractPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { job, setJobId } = useTrackedJob("tool-audio-extract");
  const [assetId, setAssetId] = usePersistentState<number | "">("tool-audio-extract:asset", "");
  const [asset, setAsset] = useState<AssetOut | null>(null);
  const [mode, setMode] = usePersistentState<"whole" | "tail">("tool-audio-extract:mode", "tail");
  const [seconds, setSeconds] = usePersistentState("tool-audio-extract:seconds", "5");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (assetId === "") {
      setAsset(null);
      return;
    }
    let alive = true;
    void api.getAsset(Number(assetId)).then(
      (loaded) => {
        if (!alive) return;
        if (loaded.kind === "video" || loaded.kind === "audio") setAsset(loaded);
        else setAssetId("");
      },
      () => {
        if (alive) setAssetId("");
      },
    );
    return () => {
      alive = false;
    };
  }, [assetId, setAssetId]);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const kind = file.type.startsWith("video/") ? "video" : "audio";
      const created = await api.uploadFileAsAsset(file, kind, true);
      return api.getAsset(created.asset_id);
    },
    onSuccess: (created) => {
      setAsset(created);
      setAssetId(created.id);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const submit = useMutation({
    mutationFn: () =>
      api.submitToolExtractAudio({
        asset_id: Number(assetId),
        mode,
        seconds: mode === "tail" ? Number(seconds) || 5 : 5,
      }),
    onSuccess: (created) => {
      setJobId(created.id);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const busy = upload.isPending || submit.isPending || (job != null && !TERMINAL_STATUSES.includes(job.status));
  const canSubmit = asset != null && assetId !== "" && !busy;

  const clear = () => {
    const current = asset;
    setAsset(null);
    setAssetId("");
    if (current?.hidden) {
      void api.deleteAsset(current.id).then(
        () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
        () => {},
      );
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="clips"
        icon={Scissors}
        title={tx("音频提取")}
        description={tx("从视频或音频中提取完整音轨，或截取固定长度尾音，用于接续生成或单独保存。")}
      />
      <SplitPane
        storageKey="tool-audio-extract"
        left={
          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{tx("输入素材")}</CardTitle>
                <CardDescription>{tx("支持视频或音频；输入没有音轨时会直接报错。")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <FileDrop
                  accept="video/*,audio/*"
                  clearAfterSelect
                  names={asset ? [assetLabel(asset)] : []}
                  title={upload.isPending ? tx("上传中…") : tx("点击或拖拽上传视频或音频")}
                  onSelect={(files) => {
                    if (files?.[0]) upload.mutate(files[0]);
                  }}
                />
                <AssetPickButton
                  kind={["video", "audio"]}
                  onPick={(assets) => {
                    if (!assets[0]) return;
                    setAsset(assets[0]);
                    setAssetId(assets[0].id);
                  }}
                />
                {asset && (
                  <div className="flex items-center gap-2 rounded-lg border border-border px-2 py-1.5">
                    <MediaThumb assetId={asset.id} kind={asset.kind} className="size-10 rounded-md" />
                    <span className="min-w-0 flex-1 truncate text-sm">{assetLabel(asset)}</span>
                    <Button size="icon" variant="ghost" aria-label={tx("移除")} onClick={clear}>
                      <Trash2 />
                    </Button>
                  </div>
                )}
                {error && <p className="text-sm text-danger">{error}</p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{tx("提取方式")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Field label={tx("范围")} hint={tx("完整音轨保留全部音频；尾音只取最后几秒。")}>
                  <select
                    className={selectClass}
                    value={mode}
                    onChange={(event) => setMode(event.target.value as "whole" | "tail")}
                  >
                    <option value="tail">{tx("固定长度尾音")}</option>
                    <option value="whole">{tx("完整音轨")}</option>
                  </select>
                </Field>
                {mode === "tail" && (
                  <Field label={tx("尾音长度（秒）")}>
                    <Input
                      type="number"
                      min={0.5}
                      max={15}
                      step={0.5}
                      value={seconds}
                      onChange={(event) => setSeconds(event.target.value)}
                    />
                  </Field>
                )}
              </CardContent>
            </Card>

            <Button className={submitButtonClass} disabled={!canSubmit} onClick={() => submit.mutate()}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {tx("开始提取")}
            </Button>
          </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="audio"
            historyKind="audio"
            jobFunction="media.extract_audio"
            emptyHint={tx("提取出的音频会出现在这里")}
          />
        }
      />
    </div>
  );
}

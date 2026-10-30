import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Download, ImageIcon, Loader2, Maximize2, Video } from "lucide-react";
import { useEffect, useState } from "react";

import { api, TERMINAL_STATUSES, type JobOut } from "@/api/client";
import {
  downloadAssetById,
  MediaLightbox,
  MediaThumb,
  type PreviewTarget,
} from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { assetTitle, formatSize, formatStepName, formatTime } from "@/lib/utils";
import { useTx } from "@/i18n/tx";

export interface MetaItem {
  label: string;
  value: string;
}

interface ResultPanelProps {
  job: JobOut | null;
  /** 结果媒体类型；null 表示文本类结果（ASR） */
  mediaKind: "image" | "audio" | "video" | null;
  /** 历史资产的 kind 筛选 */
  historyKind: string;
  /** 只看这类任务产出的资产，例如 video.i2v */
  jobKind?: string;
  meta?: MetaItem[];
  emptyHint?: string;
}

/** 生成中的精美进度展示。 */
function GeneratingState({ job }: { job: JobOut }) {
  const tx = useTx();
  const pct = Math.round(job.progress * 100);
  const step = job.steps.length > 0 ? formatStepName(String(job.steps[job.steps.length - 1].name), tx) : null;
  return (
    <div className="flex flex-col items-center gap-5 px-6 py-12">
      <div className="relative grid size-16 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/15" />
        <span className="grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary">
          <Loader2 className="size-7 animate-spin" />
        </span>
      </div>
      <div className="text-3xl font-semibold tabular-nums tracking-tight">{pct}%</div>
      <div
        className="relative h-2 w-full max-w-md overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${pct}%` }} />
        <div className="progress-shine absolute inset-0" />
      </div>
      <div className="text-sm text-muted-foreground">
        {job.status === "pending" ? tx("排队中…") : (step ?? tx("生成中…"))}
      </div>
    </div>
  );
}

/** 可点击的媒体缩略区：hover 显示提示，点击弹出全屏预览。 */
function ClickableThumb({
  target,
  onOpen,
  className,
}: {
  target: PreviewTarget;
  onOpen: (t: PreviewTarget) => void;
  className?: string;
}) {
  const tx = useTx();
  return (
    <button
      type="button"
      onClick={() => onOpen(target)}
      className="group relative block w-full overflow-hidden rounded-xl"
      title={tx("点击预览")}
    >
      <MediaThumb assetId={target.id} kind={target.kind} className={className} />
      <span className="absolute inset-0 grid place-items-center gap-1 bg-black/0 text-white opacity-0 transition group-hover:bg-black/40 group-hover:opacity-100">
        <Maximize2 className="size-6 drop-shadow" />
        <span className="text-xs font-medium drop-shadow">{tx("点击预览")}</span>
      </span>
    </button>
  );
}

export function ResultPanel({ job, mediaKind, historyKind, jobKind, meta = [], emptyHint }: ResultPanelProps) {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const historyKey = ["assets", historyKind, jobKind ?? "all"] as const;

  const { data: history } = useQuery({
    queryKey: historyKey,
    queryFn: () => api.listAssets(historyKind, undefined, jobKind),
  });

  useEffect(() => {
    if (job?.status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["assets", historyKind, jobKind ?? "all"] });
    }
  }, [job?.status, historyKind, jobKind, queryClient]);

  const running = job != null && !TERMINAL_STATUSES.includes(job.status);
  const resultAssets =
    job?.status === "succeeded"
      ? job.outputs.filter((o) => o.type === "asset" && o.asset_id)
      : [];
  const primary = resultAssets.find((o) => o.kind === mediaKind) ?? resultAssets[0];
  const textOutputs =
    job?.status === "succeeded"
      ? job.outputs.filter((o) => o.type === "text" && o.content)
      : [];

  // 仅图像/音频/视频显示缩略预览区；文本/字幕结果直接展示正文
  const primaryKind = primary?.kind ?? mediaKind;
  const primaryTarget: PreviewTarget | null =
    primary?.asset_id && primaryKind && ["image", "audio", "video"].includes(primaryKind)
      ? {
          id: primary.asset_id,
          kind: primaryKind,
          name: primary.filename,
          createdAt: job?.created_at,
        }
      : null;

  return (
    <div className="flex flex-col gap-6">
      {/* 顶部：本次结果 */}
      <Card>
        <CardContent className="flex flex-col gap-4 p-4 md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            {job && (
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{job.kind}</span>
            )}
            {meta.map(
              (m) =>
                m.value && (
                  <span key={m.label} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {m.label}：{m.value}
                  </span>
                ),
            )}
            {job && (
              <span className="text-xs text-muted-foreground">{formatTime(job.created_at)}</span>
            )}
            {primaryTarget && (
              <div className="ml-auto flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPreview(primaryTarget)}>
                  <Maximize2 /> {tx("预览")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadAssetById(primaryTarget.id, primaryTarget.name ?? `result-${primaryTarget.id}`)}
                >
                  <Download /> {tx("下载")}
                </Button>
              </div>
            )}
          </div>

          {!job ? (
            <div className="grid place-items-center gap-2 py-12 text-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-muted text-muted-foreground">
                {mediaKind === "video" ? (
                  <Video className="size-6" />
                ) : mediaKind === "audio" ? (
                  <AudioLines className="size-6" />
                ) : (
                  <ImageIcon className="size-6" />
                )}
              </span>
              <p className="text-sm text-muted-foreground">{emptyHint ?? tx("填写左侧参数开始生成")}</p>
            </div>
          ) : running ? (
            <GeneratingState job={job} />
          ) : job.status === "failed" ? (
            <div className="rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
              {job.error ?? tx("任务失败")}
            </div>
          ) : job.status === "canceled" ? (
            <div className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">{tx("任务已取消")}</div>
          ) : (
            <div className="result-in flex flex-col gap-3">
              {primaryTarget && (
                <ClickableThumb target={primaryTarget} onOpen={setPreview} className="max-h-72 w-full object-contain" />
              )}
              {textOutputs.map((t, i) => (
                <div
                  key={`text-${i}`}
                  className="max-h-64 overflow-auto rounded-xl bg-muted p-4 text-sm whitespace-pre-wrap"
                >
                  {t.content}
                </div>
              ))}
              {(resultAssets.length > 1 || (!primaryTarget && resultAssets.length > 0)) && (
                <div className="flex flex-wrap gap-2">
                  {resultAssets.map((o) => (
                    <Button
                      key={o.asset_id}
                      variant="outline"
                      size="sm"
                      onClick={() => downloadAssetById(o.asset_id!, o.filename ?? `asset-${o.asset_id}`)}
                    >
                      <Download /> {o.filename ?? o.format ?? o.asset_id}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 下方：历史资产 */}
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">{tx("历史作品")}</h2>
        {history?.length === 0 && <p className="text-sm text-muted-foreground">{tx("暂无历史记录")}</p>}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
          {history?.map((a) => {
            const name = assetTitle(a);
            return (
              <button
                key={a.id}
                type="button"
                onClick={() =>
                  setPreview({ id: a.id, kind: a.kind, name, size: a.size, createdAt: a.created_at, meta: a.meta })
                }
                className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card text-left transition-shadow hover:shadow-md"
              >
                <div className="relative aspect-video w-full overflow-hidden bg-muted/50">
                  <MediaThumb assetId={a.id} kind={a.kind} className="h-full w-full object-cover" />
                  <span className="absolute inset-0 grid place-items-center bg-black/0 opacity-0 transition group-hover:bg-black/40 group-hover:opacity-100">
                    <Maximize2 className="size-6 text-white drop-shadow" />
                  </span>
                </div>
                <div className="flex min-w-0 flex-col gap-0.5 p-2.5">
                  <span className="truncate text-sm">{name}</span>
                  <span className="text-xs text-muted-foreground">
                    {a.kind} · {formatSize(a.size)} · {formatTime(a.created_at)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

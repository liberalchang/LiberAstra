import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Download, FileText, ImageIcon, Loader2, Video, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob, TERMINAL_STATUSES, type AssetOut, type JobOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
  meta?: MetaItem[];
  emptyHint?: string;
}

const KIND_ICON = { image: ImageIcon, audio: AudioLines, video: Video, text: FileText, subtitle: FileText };

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(iso: string): string {
  return iso.slice(0, 19).replace("T", " ");
}

async function downloadAsset(assetId: number, filename: string) {
  const blob = await fetchAssetBlob(assetId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 媒体预览：按资产类型渲染 img / audio / video / 图标。 */
function MediaPreview({ assetId, kind, className }: { assetId: number; kind: string; className?: string }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!["image", "audio", "video"].includes(kind)) return;
    let revoked = false;
    fetchAssetBlob(assetId).then((b) => {
      if (!revoked) setUrl(URL.createObjectURL(b));
    });
    return () => {
      revoked = true;
    };
  }, [assetId, kind]);

  const Icon = KIND_ICON[kind as keyof typeof KIND_ICON] ?? FileText;
  if (!url) {
    return (
      <div className={cn("grid place-items-center bg-muted/50", className)}>
        <Icon className="size-10 text-muted-foreground/50" />
      </div>
    );
  }
  if (kind === "image") return <img src={url} alt="结果预览" className={cn("object-contain", className)} />;
  if (kind === "video") return <video controls src={url} className={cn("object-contain", className)} />;
  return (
    <div className={cn("flex flex-col items-center justify-center gap-4 bg-muted/50 p-6", className)}>
      <AudioLines className="size-10 text-primary" />
      <audio controls src={url} className="w-full max-w-md" />
    </div>
  );
}

/** 生成中的精美进度展示。 */
function GeneratingState({ job }: { job: JobOut }) {
  const pct = Math.round(job.progress * 100);
  const step = job.steps.length > 0 ? String(job.steps[job.steps.length - 1].name) : null;
  return (
    <div className="flex flex-col items-center gap-5 px-6 py-12">
      <div className="relative grid size-16 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/15" />
        <span className="grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary">
          <Loader2 className="size-7 animate-spin" />
        </span>
      </div>
      <div className="text-3xl font-semibold tabular-nums tracking-tight">{pct}%</div>
      <div className="relative h-2 w-full max-w-md overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${pct}%` }} />
        <div className="progress-shine absolute inset-0" />
      </div>
      <div className="text-sm text-muted-foreground">
        {job.status === "pending" ? "排队中…" : (step ?? "生成中…")}
      </div>
    </div>
  );
}

export function ResultPanel({ job, mediaKind, historyKind, meta = [], emptyHint }: ResultPanelProps) {
  const queryClient = useQueryClient();
  const [override, setOverride] = useState<AssetOut | null>(null);

  const { data: history } = useQuery({
    queryKey: ["assets", historyKind],
    queryFn: () => api.listAssets(historyKind),
  });

  useEffect(() => {
    if (job?.status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["assets", historyKind] });
    }
  }, [job?.status, historyKind, queryClient]);

  useEffect(() => {
    setOverride(null);
  }, [job?.id]);

  const running = job != null && !TERMINAL_STATUSES.includes(job.status);
  const resultAssets =
    job?.status === "succeeded"
      ? job.outputs.filter((o) => o.type === "asset" && o.asset_id)
      : [];
  const primary = resultAssets.find((o) => o.kind === mediaKind) ?? resultAssets[0];
  const textOutput = job?.status === "succeeded" ? job.outputs.find((o) => o.type === "text") : null;

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
            {primary?.asset_id && (
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                onClick={() => downloadAsset(primary.asset_id!, primary.filename ?? `result-${primary.asset_id}`)}
              >
                <Download /> 下载
              </Button>
            )}
          </div>

          {override ? (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">预览历史资产</span>
                <Button variant="ghost" size="sm" onClick={() => setOverride(null)}>
                  <X /> 返回当前结果
                </Button>
              </div>
              <MediaPreview assetId={override.id} kind={override.kind} className="w-full rounded-xl" />
            </div>
          ) : !job ? (
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
              <p className="text-sm text-muted-foreground">{emptyHint ?? "填写左侧参数开始生成"}</p>
            </div>
          ) : running ? (
            <GeneratingState job={job} />
          ) : job.status === "failed" ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500">
              {job.error ?? "任务失败"}
            </div>
          ) : job.status === "canceled" ? (
            <div className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">任务已取消</div>
          ) : (
            <div className="flex flex-col gap-3">
              {primary?.asset_id && (
                <MediaPreview assetId={primary.asset_id} kind={primary.kind ?? mediaKind ?? "image"} className="w-full rounded-xl" />
              )}
              {textOutput?.content && (
                <div className="rounded-xl bg-muted p-4 text-sm whitespace-pre-wrap">{textOutput.content}</div>
              )}
              {resultAssets.length > 1 && (
                <div className="flex flex-wrap gap-2">
                  {resultAssets.map((o) => (
                    <Button
                      key={o.asset_id}
                      variant="outline"
                      size="sm"
                      onClick={() => downloadAsset(o.asset_id!, o.filename ?? `asset-${o.asset_id}`)}
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
        <h2 className="text-sm font-medium text-muted-foreground">历史作品</h2>
        {history?.length === 0 && <p className="text-sm text-muted-foreground">暂无历史记录</p>}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
          {history?.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setOverride(a)}
              className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card text-left transition-shadow hover:shadow-md"
            >
              <div className="relative aspect-video w-full overflow-hidden bg-muted/50">
                {["image", "video"].includes(a.kind) ? (
                  <MediaPreview assetId={a.id} kind={a.kind} className="h-full w-full object-cover" />
                ) : (
                  <div className="grid h-full place-items-center">
                    {(() => {
                      const Icon = KIND_ICON[a.kind as keyof typeof KIND_ICON] ?? FileText;
                      return <Icon className="size-8 text-muted-foreground/60" />;
                    })()}
                  </div>
                )}
              </div>
              <div className="flex min-w-0 flex-col gap-0.5 p-2.5">
                <span className="truncate text-sm">{a.path.split("/").pop()}</span>
                <span className="text-xs text-muted-foreground">
                  {a.kind} · {formatSize(a.size)} · {formatTime(a.created_at)}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

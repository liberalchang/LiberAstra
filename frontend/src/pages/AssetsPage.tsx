import { Folder, FolderOpen } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api, type AssetOut } from "@/api/client";
import {
  downloadAssetById,
  MediaLightbox,
  MediaThumb,
  type PreviewTarget,
} from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { jobKindLabel } from "@/lib/jobLabels";
import { formatSize, formatTime, assetCustomName, assetDownloadName, assetSummary } from "@/lib/utils";

const KINDS = ["image", "audio", "video", "subtitle", "text"] as const;

export function AssetsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<string>("");
  const [showHidden, setShowHidden] = useState(false);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const [query, setQuery] = useState("");
  const [jobLimit, setJobLimit] = useState(24);
  const isWork = tab === "work";

  const { data: assets } = useQuery({
    queryKey: ["assets", tab, showHidden],
    queryFn: () => api.listAssets(tab && !isWork ? tab : undefined, showHidden),
    enabled: !isWork,
  });
  const { data: jobs } = useQuery({
    queryKey: ["asset-jobs", jobLimit],
    queryFn: () => api.listAssetJobs(jobLimit, 0),
    enabled: isWork,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const openPreview = (a: AssetOut) =>
    setPreview({
      id: a.id,
      kind: a.kind,
      name: assetCustomName(a.meta) ?? formatTime(a.created_at),
      size: a.size,
      createdAt: a.created_at,
      meta: a.meta,
    });

  const needle = query.trim().toLowerCase();
  const visible = (assets ?? []).filter((a) => {
    if (!needle) return true;
    const custom = assetCustomName(a.meta) ?? "";
    const summary = assetSummary(a.meta) ?? "";
    return `${custom} ${summary} ${formatTime(a.created_at)} ${a.kind}`.toLowerCase().includes(needle);
  });
  const visibleJobs = (jobs ?? []).filter((job) => {
    if (!needle) return true;
    return `${formatTime(job.created_at)} ${jobKindLabel(job.job_kind, t)} ${job.job_id} ${job.kinds.join(" ")}`
      .toLowerCase()
      .includes(needle);
  });

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader kind="library" icon={FolderOpen} title={t("assets.title")} description={t("assets.hint")} />
      <div className="flex flex-wrap gap-1">
        <Button variant={tab === "" ? "default" : "outline"} size="sm" onClick={() => setTab("")}>
          {t("assets.all")}
        </Button>
        <Button variant={isWork ? "default" : "outline"} size="sm" onClick={() => setTab("work")}>
          {t("assets.work")}
        </Button>
        {KINDS.map((k) => (
          <Button key={k} variant={tab === k ? "default" : "outline"} size="sm" onClick={() => setTab(k)}>
            {t(`assets.${k}`)}
          </Button>
        ))}
        {!isWork && (
          <label className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
            />
            {t("assets.includeHidden")}
          </label>
        )}
      </div>
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={isWork ? t("assets.searchJobs") : t("assets.search")}
        aria-label={isWork ? t("assets.searchJobs") : t("assets.search")}
      />

      {isWork ? (
        <>
          {jobs?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
          {jobs && jobs.length > 0 && visibleJobs.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("assets.noMatch")}</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleJobs.map((job) => (
              <button
                key={job.job_id}
                type="button"
                onClick={() => navigate(`/assets/jobs/${job.job_id}`)}
                className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary/50 hover:bg-muted/30"
              >
                <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Folder className="size-6" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{formatTime(job.created_at)}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {jobKindLabel(job.job_kind, t)} · {job.asset_count} {t("assets.files")}
                  </span>
                </span>
                <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {job.asset_count}
                </span>
              </button>
            ))}
          </div>
          {(jobs?.length ?? 0) >= jobLimit && jobLimit < 100 && (
            <div className="flex justify-center">
              <Button variant="outline" size="sm" onClick={() => setJobLimit((limit) => Math.min(100, limit + 24))}>
                {t("assets.loadMore")}
              </Button>
            </div>
          )}
        </>
      ) : (
        <>
          {assets?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
          {assets && assets.length > 0 && visible.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("assets.noMatch")}</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((a) => {
              const custom = assetCustomName(a.meta);
              const summary = assetSummary(a.meta);
              const title = custom ?? formatTime(a.created_at);
              return (
                <Card key={a.id}>
                  <CardContent className="flex flex-col gap-2 p-3">
                    <button
                      type="button"
                      onClick={() => openPreview(a)}
                      className="group relative block w-full overflow-hidden rounded-lg"
                      title={t("common.preview")}
                    >
                      <div className="aspect-video w-full overflow-hidden bg-muted/50">
                        <MediaThumb assetId={a.id} kind={a.kind} className="h-full w-full object-cover" />
                      </div>
                      <span className="absolute inset-0 grid place-items-center gap-1 rounded-lg bg-black/0 text-white opacity-0 transition group-hover:bg-black/40 group-hover:opacity-100">
                        <Eye className="size-6 drop-shadow" />
                        <span className="text-xs font-medium drop-shadow">{t("common.preview")}</span>
                      </span>
                    </button>
                    <div className="min-w-0">
                      <div className="truncate text-sm" title={title}>
                        {title}
                      </div>
                      {summary && summary !== title && (
                        <div className="truncate text-xs text-muted-foreground" title={summary}>
                          {summary}
                        </div>
                      )}
                      <div className="text-xs text-muted-foreground">
                        {a.kind} · {formatSize(a.size)}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <Button variant="outline" size="sm" onClick={() => openPreview(a)} aria-label={t("common.preview")}>
                        <Eye /> {t("common.preview")}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => downloadAssetById(a.id, assetDownloadName(a))}
                        aria-label={t("common.download")}
                      >
                        <Download /> {t("common.download")}
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => remove.mutate(a.id)} aria-label={t("common.delete")}>
                        <Trash2 /> {t("common.delete")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

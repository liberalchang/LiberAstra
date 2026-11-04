import { ArrowLeft, Download, Eye, FolderOpen, ListTodo } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api, type AssetOut } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import {
  downloadAssetById,
  kindLabel,
  MediaLightbox,
  MediaThumb,
  type PreviewTarget,
} from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { jobKindLabel } from "@/lib/jobLabels";
import { assetCustomName, assetDownloadName, assetSummary, formatSize, formatTime } from "@/lib/utils";

export function AssetJobPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { jobId = "" } = useParams();
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const [assetLimit, setAssetLimit] = useState(50);

  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId),
    enabled: Boolean(jobId),
  });
  const { data: assets } = useQuery({
    queryKey: ["job-assets", jobId, assetLimit],
    queryFn: () => api.listJobAssets(jobId, assetLimit, 0),
    enabled: Boolean(jobId),
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

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader
        kind="library"
        icon={FolderOpen}
        title={job ? jobKindLabel(job.kind, t) : t("assets.jobAssets")}
        description={job ? `${formatTime(job.created_at)} · ${job.id.slice(0, 8)}` : jobId}
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => navigate("/assets")}>
          <ArrowLeft /> {t("assets.back")}
        </Button>
        <Button variant="outline" size="sm" onClick={() => navigate("/jobs")}>
          <ListTodo /> {t("assets.viewJob")}
        </Button>
      </div>
      {assets?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(assets ?? []).map((a) => {
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
                    {kindLabel(a.kind)} · {formatSize(a.size)}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button variant="outline" size="sm" onClick={() => openPreview(a)}>
                    <Eye /> {t("common.preview")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => downloadAssetById(a.id, assetDownloadName(a))}
                  >
                    <Download /> {t("common.download")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      {(assets?.length ?? 0) >= assetLimit && assetLimit < 200 && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => setAssetLimit((limit) => Math.min(200, limit + 50))}>
            {t("assets.loadMore")}
          </Button>
        </div>
      )}
      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

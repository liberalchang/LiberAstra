import { FolderOpen } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type AssetOut } from "@/api/client";
import {
  downloadAssetById,
  MediaLightbox,
  MediaThumb,
  type PreviewTarget,
} from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatSize, assetDownloadName, assetSummary, assetTitle } from "@/lib/utils";

const KINDS = ["image", "audio", "video", "subtitle", "text"] as const;

export function AssetsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<string>("");
  const [showHidden, setShowHidden] = useState(false);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);

  const { data: assets } = useQuery({
    queryKey: ["assets", kind, showHidden],
    queryFn: () => api.listAssets(kind || undefined, showHidden),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const openPreview = (a: AssetOut) =>
    setPreview({
      id: a.id,
      kind: a.kind,
      name: assetTitle(a),
      size: a.size,
      createdAt: a.created_at,
      meta: a.meta,
    });

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader kind="library" icon={FolderOpen} title={t("assets.title")} description={t("assets.hint")} />
      <div className="flex flex-wrap gap-1">
          <Button variant={kind === "" ? "default" : "outline"} size="sm" onClick={() => setKind("")}>
            {t("assets.all")}
          </Button>
          {KINDS.map((k) => (
            <Button key={k} variant={kind === k ? "default" : "outline"} size="sm" onClick={() => setKind(k)}>
              {t(`assets.${k}`)}
            </Button>
          ))}
          <label className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
            />
            {t("assets.includeHidden")}
          </label>
      </div>
      {assets?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {assets?.map((a) => (
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
                <div className="truncate text-sm" title={assetSummary(a.meta) ?? undefined}>
                  {assetTitle(a)}
                </div>
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
        ))}
      </div>

      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

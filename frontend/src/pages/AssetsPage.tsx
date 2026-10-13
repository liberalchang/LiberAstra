import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, fetchAssetBlob, type AssetOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const KINDS = ["image", "audio", "video", "subtitle", "text"] as const;

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function AssetPreview({ asset }: { asset: AssetOut }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!["image", "audio", "video"].includes(asset.kind)) return;
    let revoked = false;
    fetchAssetBlob(asset.id).then((b) => {
      if (!revoked) setUrl(URL.createObjectURL(b));
    });
    return () => {
      revoked = true;
    };
  }, [asset.id, asset.kind]);

  if (!url) return null;
  if (asset.kind === "image") return <img src={url} alt="" className="max-h-40 rounded" />;
  if (asset.kind === "audio") return <audio controls src={url} className="w-full" />;
  if (asset.kind === "video") return <video controls src={url} className="max-h-40 rounded" />;
  return null;
}

export function AssetsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<string>("");

  const { data: assets } = useQuery({
    queryKey: ["assets", kind],
    queryFn: () => api.listAssets(kind || undefined),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const download = async (asset: AssetOut) => {
    const blob = await fetchAssetBlob(asset.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = asset.path.split("/").pop() ?? `asset-${asset.id}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">{t("assets.title")}</h1>
        <div className="flex gap-1">
          <Button variant={kind === "" ? "default" : "outline"} size="sm" onClick={() => setKind("")}>
            {t("assets.all")}
          </Button>
          {KINDS.map((k) => (
            <Button key={k} variant={kind === k ? "default" : "outline"} size="sm" onClick={() => setKind(k)}>
              {t(`assets.${k}`)}
            </Button>
          ))}
        </div>
      </div>
      {assets?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {assets?.map((a) => (
          <Card key={a.id}>
            <CardContent className="flex flex-col gap-2 p-3">
              <AssetPreview asset={a} />
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm">{a.path.split("/").pop()}</div>
                  <div className="text-xs text-muted-foreground">
                    {a.kind} · {formatSize(a.size)}
                  </div>
                </div>
                <div className="flex shrink-0">
                  <Button variant="ghost" size="icon" onClick={() => download(a)} title={t("common.download")}>
                    <Download />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => remove.mutate(a.id)} title={t("common.delete")}>
                    <Trash2 />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

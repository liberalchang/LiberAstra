import { ListChecks } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, fetchAssetBlob, TERMINAL_STATUSES, type JobOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn, formatStepName } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  succeeded: "text-success",
  failed: "text-danger",
  canceled: "text-muted-foreground",
  running: "text-info",
  pending: "text-muted-foreground",
};

export function JobsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listAllJobs(),
    refetchInterval: (query) =>
      query.state.data?.some((j) => !TERMINAL_STATUSES.includes(j.status)) ? 1500 : false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["jobs"] });
  const cancel = useMutation({ mutationFn: (id: string) => api.cancelJob(id), onSuccess: invalidate });
  const retry = useMutation({ mutationFn: (id: string) => api.retryJob(id), onSuccess: invalidate });

  const download = async (assetId: number, filename: string) => {
    const blob = await fetchAssetBlob(assetId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader kind="jobs" icon={ListChecks} title={t("jobs.title")} description={t("jobs.hint")} />
      {jobs?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
      {jobs?.map((j: JobOut) => (
        <Card key={j.id}>
          <CardContent className="flex flex-col gap-2 p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <code className="text-xs text-muted-foreground">{j.id.slice(0, 8)}</code>
              <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{j.kind}</span>
              <span className={cn("text-sm", STATUS_COLOR[j.status])}>{t(`common.${j.status}`)}</span>
              <div
                className="h-1.5 min-w-24 flex-1 basis-32 overflow-hidden rounded bg-muted"
                role="progressbar"
                aria-valuenow={Math.round(j.progress * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${Math.round(j.progress * 100)}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground">{j.created_at.slice(0, 19).replace("T", " ")}</span>
              {!TERMINAL_STATUSES.includes(j.status) && (
                <Button variant="outline" size="sm" onClick={() => cancel.mutate(j.id)}>
                  <X /> {t("common.cancel")}
                </Button>
              )}
              {TERMINAL_STATUSES.includes(j.status) && (
                <Button variant="outline" size="sm" onClick={() => retry.mutate(j.id)}>
                  <RotateCcw /> {t("common.retry")}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(expanded === j.id ? null : j.id)}
              >
                {t("jobs.detail")}
              </Button>
            </div>
            {expanded === j.id && (
              <div className="flex flex-col gap-2 border-t border-border pt-2">
                {j.error && <p className="text-sm text-danger">{j.error}</p>}
                {j.steps.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {j.steps.map((s) => formatStepName(String(s.name))).join(" → ")}
                  </p>
                )}
                {j.outputs.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {j.outputs
                      .filter((o) => o.type === "asset" && o.asset_id)
                      .map((o) => (
                        <Button
                          key={o.asset_id}
                          variant="outline"
                          size="sm"
                          onClick={() => download(o.asset_id!, o.filename ?? `asset-${o.asset_id}`)}
                        >
                          {o.filename ?? `${t("jobs.outputs")} ${o.asset_id}`}
                        </Button>
                      ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

import { ListTodo } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, fetchAssetBlob, type JobOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { cn, formatStepName } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  succeeded: "text-success",
  failed: "text-danger",
  canceled: "text-muted-foreground",
  running: "text-info",
  pending: "text-muted-foreground",
};

type JobFilter = "all" | "active" | "failed" | "done";

const KIND_LABEL: Record<string, string> = {
  "image.generate": "nav.imageGen",
  "image.edit": "nav.imageEdit",
  "video.quick": "nav.videoQuick",
  "video.i2v": "nav.i2v",
  "video.avatar": "nav.avatar",
  "video.motion": "nav.motion",
  "video.assets": "nav.videoAssets",
  "video.assets.script": "jobs.script",
  "canvas.node": "jobs.node",
  "media.concat": "jobs.concat",
  "tts.synthesize": "nav.tts",
  "asr.transcribe": "nav.asr",
  "character.generate": "nav.characters",
  "prompt.optimize": "nav.prompts",
  "llm.chat": "jobs.chat",
};

const SUMMARY_KEYS = ["prompt", "text", "title", "topic", "script"];

function jobSummary(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  for (const key of SUMMARY_KEYS) {
    const value = params[key];
    if (typeof value === "string" && value.trim()) {
      const text = value.replace(/\s+/g, " ").trim();
      return text.length > 42 ? `${text.slice(0, 42)}…` : text;
    }
  }
  return "";
}

function matchesFilter(status: JobOut["status"], filter: JobFilter): boolean {
  if (filter === "all") return true;
  if (filter === "active") return status === "pending" || status === "running";
  if (filter === "failed") return status === "failed" || status === "canceled";
  return status === "succeeded";
}

export function JobsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<JobFilter>("all");

  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listAllJobs(),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "pending" || j.status === "running") ? 1500 : false,
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

  const visible = (jobs ?? []).filter((j) => matchesFilter(j.status, filter));

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader kind="jobs" icon={ListTodo} title={t("jobs.title")} description={t("jobs.hint")} />
      <Segmented
        ariaLabel={t("jobs.filterLabel")}
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: t("jobs.filterAll") },
          { value: "active", label: t("jobs.filterActive") },
          { value: "failed", label: t("jobs.filterFailed") },
          { value: "done", label: t("jobs.filterDone") },
        ]}
      />
      {jobs && visible.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
      {visible.map((j: JobOut) => {
        const active = j.status === "pending" || j.status === "running";
        const canRetry = j.status === "failed" || j.status === "canceled";
        const summary = jobSummary(j.params);
        const kindLabel = KIND_LABEL[j.kind] ? t(KIND_LABEL[j.kind]) : j.kind;
        return (
        <Card key={j.id}>
          <CardContent className="flex flex-col gap-2 p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="text-sm font-medium">{kindLabel}</span>
              {summary && <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">{summary}</span>}
              <span className={cn("text-sm", STATUS_COLOR[j.status])}>{t(`common.${j.status}`)}</span>
              {active && (
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
              )}
              <span className="text-xs text-muted-foreground">{j.created_at.slice(0, 19).replace("T", " ")}</span>
              {active && (
                <Button variant="outline" size="sm" onClick={() => cancel.mutate(j.id)}>
                  <X /> {t("common.cancel")}
                </Button>
              )}
              {canRetry && (
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
            {j.status === "failed" && j.error && (
              <p className="text-sm text-danger">{j.error}</p>
            )}
            {expanded === j.id && (
              <div className="flex flex-col gap-2 border-t border-border pt-2">
                <p className="text-xs text-muted-foreground">
                  {t("jobs.id")} {j.id.slice(0, 8)} · {j.kind}
                </p>
                {j.error && j.status !== "failed" && <p className="text-sm text-danger">{j.error}</p>}
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
        );
      })}
    </div>
  );
}

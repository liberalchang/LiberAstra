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
import { cn, formatStepName, readableText } from "@/lib/utils";
import { explainJobError } from "@/lib/jobError";
import { useTx } from "@/i18n/tx";

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

function paramText(params: Record<string, unknown> | undefined, key: string): string {
  const value = params?.[key];
  return typeof value === "string" ? readableText(value) : "";
}

function jobSummary(params: Record<string, unknown> | undefined): string {
  const inputs = params?.inputs;
  const nested =
    inputs && typeof inputs === "object" ? paramText(inputs as Record<string, unknown>, "prompt") : "";
  const text = [...SUMMARY_KEYS.map((key) => paramText(params, key)), nested].find(Boolean) ?? "";
  return text.length > 42 ? `${text.slice(0, 42)}…` : text;
}

function matchesFilter(status: JobOut["status"], filter: JobFilter): boolean {
  if (filter === "all") return true;
  if (filter === "active") return status === "pending" || status === "running";
  if (filter === "failed") return status === "failed" || status === "canceled";
  return status === "succeeded";
}

export function JobsPage() {
  const { t } = useTranslation();
  const tx = useTx();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<JobFilter>("all");

  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listAllJobs(),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "pending" || j.status === "running") ? 1500 : false,
  });
  const needsCanvas = (jobs ?? []).some((job) => paramText(job.params, "canvas_id"));
  const { data: canvases } = useQuery({
    queryKey: ["canvases"],
    queryFn: () => api.listCanvases(),
    enabled: needsCanvas,
  });
  const canvasNames = new Map((canvases ?? []).map((canvas) => [canvas.id, canvas.name]));

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
        const canvasId = paramText(j.params, "canvas_id");
        const canvasName = paramText(j.params, "canvas_name") || (canvasId ? canvasNames.get(canvasId) ?? "" : "");
        const node =
          paramText(j.params, "node_label") || paramText(j.params, "workflow") || paramText(j.params, "model");
        const kindLabel = KIND_LABEL[j.kind] ? t(KIND_LABEL[j.kind]) : j.kind;
        const title = canvasName ? `${canvasName} · ${node || kindLabel}` : kindLabel;
        const explained = j.error ? explainJobError(j.error) : null;
        return (
        <Card key={j.id}>
          <CardContent className="flex flex-col gap-2 p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="text-sm font-medium">{title}</span>
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
                  <RotateCcw /> {t("jobs.retrySame")}
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
            {j.status === "failed" && explained && (
              <p className="line-clamp-3 text-sm text-danger">{tx(explained.summary)}</p>
            )}
            {expanded === j.id && (
              <div className="flex flex-col gap-2 border-t border-border pt-2">
                <p className="text-xs text-muted-foreground">
                  {t("jobs.id")} {j.id.slice(0, 8)} · {j.kind}
                </p>
                {explained && <p className="whitespace-pre-wrap break-words text-sm text-danger">{explained.detail}</p>}
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

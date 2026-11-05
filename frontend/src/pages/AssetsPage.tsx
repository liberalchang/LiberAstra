import { CheckSquare, Folder, FolderOpen, FolderPlus, Loader2, Upload } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, type AssetOut } from "@/api/client";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  downloadAssetById,
  MediaLightbox,
  MediaThumb,
  type PreviewTarget,
} from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { inferAssetKind } from "@/lib/fileAccept";
import { jobKindLabel } from "@/lib/jobLabels";
import { cn, formatSize, formatTime, assetCustomName, assetDownloadName, assetSummary } from "@/lib/utils";

const KINDS = ["image", "audio", "video", "subtitle", "text"] as const;

export function AssetsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "";
  const queryClient = useQueryClient();
  const [showHidden, setShowHidden] = useState(false);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const [query, setQuery] = useState("");
  const [jobLimit, setJobLimit] = useState(24);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState<"download" | "delete" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const isWork = tab === "work";
  const setTab = (value: string) => {
    setSearchParams(value ? { tab: value } : {}, { replace: true });
    setSelectionMode(false);
    setSelectedJobs(new Set());
    setBulkError(null);
  };

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

  const publish = useMutation({
    mutationFn: (id: number) => api.publishAsset(id),
    onSuccess: () => {
      setNotice(t("assets.published"));
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
    onError: (error: Error) => setUploadError(error.message),
  });

  const uploadFiles = async (files: File[]) => {
    setUploadError(null);
    const unsupported: string[] = [];
    let uploaded = 0;
    for (const file of files) {
      const kind = inferAssetKind(file);
      if (!kind) {
        unsupported.push(file.name);
        continue;
      }
      try {
        await api.uploadFileAsAsset(file, kind);
        uploaded += 1;
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : String(error));
      }
    }
    if (uploaded > 0) {
      setNotice(t("assets.uploaded", { n: uploaded }));
      setTab("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assets"] }),
        queryClient.invalidateQueries({ queryKey: ["asset-jobs"] }),
      ]);
    }
    if (unsupported.length > 0) {
      setUploadError(t("assets.unsupported", { names: unsupported.join("、") }));
    }
  };

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
  const selectedJobRows = (jobs ?? []).filter((job) => selectedJobs.has(job.job_id));
  const selectedAssetCount = selectedJobRows.reduce((sum, job) => sum + job.asset_count, 0);

  useEffect(() => {
    setSelectionMode(false);
    setSelectedJobs(new Set());
    setBulkError(null);
  }, [tab]);

  useEffect(() => {
    if (!isWork || !jobs) return;
    setSelectedJobs((previous) => {
      const next = new Set(
        [...previous].filter((jobId) => jobs.some((job) => job.job_id === jobId)),
      );
      return next.size === previous.size ? previous : next;
    });
  }, [isWork, jobs]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const toggleJob = (jobId: string) => {
    setSelectedJobs((previous) => {
      const next = new Set(previous);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
    setBulkError(null);
  };

  const exitSelection = () => {
    setSelectionMode(false);
    setSelectedJobs(new Set());
    setBulkError(null);
  };

  const selectAllJobs = () => {
    setSelectedJobs(new Set(visibleJobs.map((job) => job.job_id)));
    setBulkError(null);
  };

  const downloadSelected = async () => {
    if (!selectedJobs.size) return;
    setBulkBusy("download");
    setBulkError(null);
    setNotice(t("assets.downloadStarted"));
    try {
      const url = await api.getAssetJobsDownloadUrl([...selectedJobs]);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "liberastra-jobs.zip";
      anchor.click();
    } catch (error) {
      setNotice(null);
      setBulkError(error instanceof Error ? error.message : String(error));
    } finally {
      setBulkBusy(null);
    }
  };

  const deleteSelected = async () => {
    if (!selectedJobs.size) return;
    setBulkBusy("delete");
    setBulkError(null);
    try {
      const result = await api.deleteAssetJobs([...selectedJobs]);
      setConfirmDelete(false);
      exitSelection();
      setNotice(t("assets.bulkDeleted", { jobs: result.jobs, assets: result.assets }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["asset-jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["assets"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    } catch (error) {
      setBulkError(error instanceof Error ? error.message : String(error));
    } finally {
      setBulkBusy(null);
    }
  };

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader kind="library" icon={FolderOpen} title={t("assets.title")} description={t("assets.hint")} />
      <input
        ref={uploadInputRef}
        type="file"
        multiple
        accept="image/*,video/*,audio/*,.srt,.vtt,.txt,.md,.json,.csv"
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) void uploadFiles(files);
        }}
      />
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
        <div className="ml-auto flex items-center gap-3">
          {!isWork && (
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={showHidden}
                onChange={(e) => setShowHidden(e.target.checked)}
              />
              {t("assets.includeHidden")}
            </label>
          )}
          <Button variant="outline" size="sm" onClick={() => uploadInputRef.current?.click()}>
            <Upload /> {t("assets.upload")}
          </Button>
        </div>
      </div>
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={isWork ? t("assets.searchJobs") : t("assets.search")}
        aria-label={isWork ? t("assets.searchJobs") : t("assets.search")}
      />

      {isWork && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-2">
          {!selectionMode ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectionMode(true)}
                disabled={!jobs?.length}
              >
                <CheckSquare /> {t("assets.select")}
              </Button>
              <span className="text-xs text-muted-foreground">{t("assets.selectHint")}</span>
            </>
          ) : (
            <>
              <span className="text-sm font-medium">
                {t("assets.selected", { n: selectedJobs.size })}
              </span>
              <Button size="sm" variant="ghost" onClick={selectAllJobs} disabled={!visibleJobs.length}>
                {t("assets.selectAllLoaded")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void downloadSelected()}
                disabled={!selectedJobs.size || bulkBusy !== null}
              >
                {bulkBusy === "download" ? <Loader2 className="animate-spin" /> : <Download />}
                {t("common.download")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-danger"
                onClick={() => setConfirmDelete(true)}
                disabled={!selectedJobs.size || bulkBusy !== null}
              >
                <Trash2 /> {t("common.delete")}
              </Button>
              <Button size="sm" variant="ghost" onClick={exitSelection} disabled={bulkBusy !== null}>
                {t("common.cancel")}
              </Button>
            </>
          )}
        </div>
      )}
      {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
      {bulkError && !confirmDelete && <p role="alert" className="text-sm text-danger">{bulkError}</p>}
      {uploadError && <p role="alert" className="text-sm text-danger">{uploadError}</p>}

      {isWork ? (
        <>
          {jobs?.length === 0 && <p className="text-sm text-muted-foreground">{t("common.empty")}</p>}
          {jobs && jobs.length > 0 && visibleJobs.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("assets.noMatch")}</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleJobs.map((job) => {
              const checked = selectedJobs.has(job.job_id);
              return (
                <div
                  key={job.job_id}
                  className={cn(
                    "relative rounded-xl border border-border bg-card transition-colors",
                    checked ? "border-primary bg-primary/5" : "hover:border-primary/50",
                  )}
                >
                  {selectionMode && (
                    <label className="absolute left-2 top-2 z-10 grid size-6 place-items-center rounded-md bg-card/90">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleJob(job.job_id)}
                        aria-label={`${t("assets.select")} ${formatTime(job.created_at)}`}
                      />
                    </label>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      selectionMode
                        ? toggleJob(job.job_id)
                        : navigate(`/assets/jobs/${job.job_id}`)
                    }
                    className={cn(
                      "flex w-full items-center gap-3 p-4 text-left",
                      selectionMode && "pl-10",
                    )}
                  >
                    <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                      <Folder className="size-6" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {formatTime(job.created_at)}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {jobKindLabel(job.job_kind, t)} · {job.asset_count} {t("assets.files")}
                      </span>
                    </span>
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {job.asset_count}
                    </span>
                  </button>
                </div>
              );
            })}
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
                      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                        <span>{a.kind} · {formatSize(a.size)}</span>
                        {a.hidden && (
                          <span className="rounded bg-warning/15 px-1.5 py-0.5 text-[10px] text-warning">
                            {t("assets.hidden")}
                          </span>
                        )}
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
                      {a.hidden && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => publish.mutate(a.id)}
                          disabled={publish.isPending}
                          aria-label={`${t("assets.publish")} ${title}`}
                        >
                          <FolderPlus /> {t("assets.publish")}
                        </Button>
                      )}
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

      {confirmDelete && (
        <ConfirmDialog
          title={t("assets.bulkDeleteTitle")}
          message={t("assets.bulkDeleteMessage", {
            jobs: selectedJobs.size,
            assets: selectedAssetCount,
          })}
          confirmLabel={t("common.delete")}
          danger
          busy={bulkBusy === "delete"}
          error={bulkError}
          onConfirm={() => void deleteSelected()}
          onClose={() => {
            if (bulkBusy === "delete") return;
            setConfirmDelete(false);
            setBulkError(null);
          }}
        />
      )}
      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

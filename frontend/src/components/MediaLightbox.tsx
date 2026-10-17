import { AudioLines, Download, FileText, ImageIcon, Loader2, Video, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { assetDownloadName, assetSummary, assetTitle, cn, formatSize, formatTime } from "@/lib/utils";

export interface PreviewTarget {
  id: number;
  kind: string;
  name?: string;
  size?: number;
  createdAt?: string;
  meta?: Record<string, unknown> | null;
}

const KIND_ICON = { image: ImageIcon, audio: AudioLines, video: Video, text: FileText, subtitle: FileText };

const KIND_LABEL: Record<string, string> = {
  image: "图像",
  audio: "音频",
  video: "视频",
  text: "文本",
  subtitle: "字幕",
};

/** meta 字段的中文标签与展示顺序（prompt/text/title 作为摘要单独展示）。 */
const META_LABELS: [string, string][] = [
  ["template", "模板"],
  ["workflow", "画面工作流"],
  ["tts_workflow", "配音工作流"],
  ["model", "模型"],
  ["llm_provider", "脚本服务"],
  ["llm_model", "脚本模型"],
  ["size", "尺寸"],
  ["aspect", "画幅"],
  ["seed", "种子"],
  ["voice", "音色"],
  ["bgm", "背景音乐"],
  ["format", "格式"],
  ["frames", "帧数"],
  ["provider", "服务"],
  ["language", "语言"],
  ["source_name", "源文件"],
];

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind;
}

export async function downloadAssetById(assetId: number, filename: string) {
  const blob = await fetchAssetBlob(assetId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 加载资产内容的 object URL；不可预览类型返回 null。 */
function useAssetUrl(assetId: number | null, kind: string | null) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (assetId == null || !kind || !["image", "audio", "video"].includes(kind)) return;
    let revoked = false;
    let objectUrl: string | null = null;
    setUrl(null);
    fetchAssetBlob(assetId)
      .then((b) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(b);
        setUrl(objectUrl);
      })
      .catch(() => {
        /* 加载失败时保持占位图标 */
      });
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [assetId, kind]);

  return url;
}

const TEXTUAL_KINDS = ["text", "subtitle"];

/** 加载文本类资产（txt/json/srt/vtt）的正文；非文本类型返回 null。 */
function useAssetText(assetId: number | null, kind: string | null) {
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    if (assetId == null || !kind || !TEXTUAL_KINDS.includes(kind)) return;
    let alive = true;
    setText(null);
    fetchAssetBlob(assetId)
      .then((b) => b.text())
      .then((t) => {
        if (alive) setText(t);
      })
      .catch(() => {
        /* 加载失败时保持空态 */
      });
    return () => {
      alive = false;
    };
  }, [assetId, kind]);

  return text;
}

/**
 * 非交互式缩略预览：图片直接显示，视频取首帧，音频/文本显示图标。
 * 用于结果卡片与资产列表，点击交互由外层按钮负责（弹出 MediaLightbox）。
 */
export function MediaThumb({ assetId, kind, className }: { assetId: number; kind: string; className?: string }) {
  const url = useAssetUrl(assetId, kind);
  const Icon = KIND_ICON[kind as keyof typeof KIND_ICON] ?? FileText;

  if (!url) {
    return (
      <div className={cn("grid place-items-center bg-muted/50", className)}>
        <Icon className="size-10 text-muted-foreground/50" />
      </div>
    );
  }
  if (kind === "image") return <img src={url} alt="预览" className={cn("object-cover", className)} />;
  if (kind === "video") {
    return <video src={url} muted playsInline preload="metadata" className={cn("object-cover", className)} />;
  }
  return (
    <div className={cn("grid place-items-center bg-muted/50", className)}>
      <AudioLines className="size-10 text-primary/70" />
    </div>
  );
}

/** 全屏弹窗预览：图片放大查看，视频/音频弹出播放。Esc 或点击遮罩关闭。 */
export function MediaLightbox({ target, onClose }: { target: PreviewTarget | null; onClose: () => void }) {
  const url = useAssetUrl(target?.id ?? null, target?.kind ?? null);
  const text = useAssetText(target?.id ?? null, target?.kind ?? null);
  const targetId = target?.id ?? null;

  // 拉取资产详情：补齐 meta / path，用于参数展示与友好下载名
  const { data: detail } = useQuery({
    queryKey: ["asset", targetId],
    queryFn: () => api.getAsset(targetId!),
    enabled: targetId != null,
  });

  // Esc 关闭 + 锁定背景滚动
  useEffect(() => {
    if (targetId == null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId]);

  if (!target) return null;

  const meta = detail?.meta ?? target.meta ?? null;
  const summary = assetSummary(meta);
  const name = target.name ?? (detail ? assetTitle(detail) : `asset-${target.id}`);
  const size = target.size ?? detail?.size;
  const createdAt = target.createdAt ?? detail?.created_at;
  const downloadName = detail ? assetDownloadName(detail) : name;
  const duration = typeof meta?.duration_s === "number" ? `${meta.duration_s}s` : null;
  const previewable = ["image", "audio", "video"].includes(target.kind);
  const textual = TEXTUAL_KINDS.includes(target.kind);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" onClick={onClose}>
      <div className="lightbox-backdrop absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className="lightbox-pop relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl md:flex-row"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={name}
      >
        <Button
          variant="outline"
          size="icon"
          className="absolute right-3 top-3 z-10 rounded-full bg-card/90 shadow-md"
          onClick={onClose}
          title="关闭 (Esc)"
        >
          <X />
        </Button>

        {/* 媒体区 */}
        <div className="grid min-h-56 flex-1 place-items-center overflow-hidden bg-black/90 md:max-h-[90vh]">
          {previewable && !url ? (
            <Loader2 className="size-8 animate-spin text-white/60" />
          ) : target.kind === "image" ? (
            <img src={url!} alt={name} className="max-h-[60vh] w-full object-contain md:max-h-[90vh]" />
          ) : target.kind === "video" ? (
            <video src={url!} controls autoPlay className="max-h-[60vh] w-full object-contain md:max-h-[90vh]" />
          ) : target.kind === "audio" ? (
            <div className="flex w-full max-w-md flex-col items-center gap-5 p-8">
              <span className="grid size-20 place-items-center rounded-full bg-primary/20 text-primary">
                <AudioLines className="size-10" />
              </span>
              <audio src={url!} controls autoPlay className="w-full" />
            </div>
          ) : textual ? (
            <div className="max-h-[60vh] w-full overflow-auto p-5 md:max-h-[90vh]">
              {text == null ? (
                <div className="grid place-items-center py-10">
                  <Loader2 className="size-8 animate-spin text-white/60" />
                </div>
              ) : (
                <pre className="whitespace-pre-wrap break-all font-mono text-sm leading-relaxed text-white/90">
                  {text}
                </pre>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <FileText className="size-12 text-white/50" />
              <p className="text-sm text-white/70">此类型暂不支持在线预览，可直接下载查看</p>
            </div>
          )}
        </div>

        {/* 信息区 */}
        <div className="flex w-full shrink-0 flex-col gap-4 p-5 md:w-72 md:overflow-y-auto">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-primary">快速预览</span>
            <h2 className="break-all text-lg font-semibold leading-snug">{name}</h2>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{kindLabel(target.kind)}</span>
            {size != null && (
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {formatSize(size)}
              </span>
            )}
            {createdAt && (
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {formatTime(createdAt)}
              </span>
            )}
            {duration && (
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                耗时 {duration}
              </span>
            )}
          </div>
          {summary && summary !== name && (
            <p className="break-all rounded-xl bg-muted/60 p-3 text-xs leading-relaxed text-muted-foreground">
              {summary}
            </p>
          )}
          {meta && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
              {META_LABELS.map(([key, label]) => {
                const v = meta[key];
                if (v == null || v === "") return null;
                return (
                  <div key={key} className="contents">
                    <dt className="shrink-0 text-muted-foreground">{label}</dt>
                    <dd className="break-all">{String(v)}</dd>
                  </div>
                );
              })}
            </dl>
          )}
          <div className="mt-auto flex flex-col gap-2">
            <Button onClick={() => downloadAssetById(target.id, downloadName)}>
              <Download /> 下载
            </Button>
            <Button variant="outline" onClick={onClose}>
              关闭
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

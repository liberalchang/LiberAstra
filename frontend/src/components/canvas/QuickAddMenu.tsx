/** 快速建点菜单（两 tab）：
 * - 功能：按包能力分类展示「所属」分组,点击直接把功能节点(带所属+组内第一个包)加进画布
 * - 输入输出:图片/视频/音频/文本输入 + 视频/音频合成
 */
import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  Clapperboard,
  FileText,
  Image as ImageIcon,
  Mic,
  Video,
  Zap,
} from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/api/client";
import type { CanvasNodeKind, MediaKind, SpeechMode } from "@/canvas/types";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

export interface QuickAddPick {
  kind: CanvasNodeKind;
  mediaKind?: MediaKind;
  /** 功能节点:预选所属分组(落点即生效,组内第一个包默认加载) */
  group?: string;
  /** 语音节点模式 */
  speechMode?: SpeechMode;
}

/** 功能节点只分三大类:图片 / 视频 / 语音。capability → 桶。 */
const CAPABILITY_BUCKET: Record<string, "image" | "video"> = {
  t2i: "image",
  i2i: "image",
  upscale: "image",
  t2v: "video",
  i2v: "video",
  avatar: "video",
  motion: "video",
};

const IO_ITEMS: { kind: CanvasNodeKind; mediaKind?: MediaKind; icon: typeof ImageIcon; label: string }[] = [
  { kind: "input", mediaKind: "image", icon: ImageIcon, label: "图片输入" },
  { kind: "input", mediaKind: "video", icon: Video, label: "视频输入" },
  { kind: "input", mediaKind: "audio", icon: AudioLines, label: "音频输入" },
  { kind: "input", mediaKind: "text", icon: FileText, label: "文本输入" },
  { kind: "concat", mediaKind: "video", icon: Clapperboard, label: "视频合成" },
  { kind: "concat", mediaKind: "audio", icon: AudioLines, label: "音频合成" },
];

const SPEECH_ITEMS: { mode: SpeechMode; icon: typeof Mic; label: string; hint: string }[] = [
  { mode: "tts", icon: AudioLines, label: "文字转语音", hint: "文本 → 音频" },
  { mode: "asr", icon: Mic, label: "语音转文字", hint: "音频 → 文本" },
];

export function QuickAddMenu({
  x,
  y,
  onPick,
  onClose,
}: {
  /** 屏幕坐标（相对画布容器） */
  x: number;
  y: number;
  onPick: (pick: QuickAddPick) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const [tab, setTab] = useState<"function" | "io">("function");
  const { data: groups } = useQuery({ queryKey: ["canvas-groups"], queryFn: api.getCanvasGroups });
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  /** 所属按「组内第一个包的能力」归入图片/视频桶;语音是固定两项。 */
  const sections = useMemo(() => {
    const byBucket = new Map<"image" | "video", string[]>();
    for (const [group, packNames] of Object.entries(groups ?? {})) {
      const first = packNames[0] ? packs?.find((p) => p.name === packNames[0]) : null;
      let bucket = first ? CAPABILITY_BUCKET[first.capability] : undefined;
      if (!bucket && first) {
        // analysis 等未映射能力:按首个媒体输入类型归类
        const spec = Object.values(first.inputs).find((s) => s.type === "video" || s.type === "image");
        bucket = spec?.type === "video" ? "video" : "image";
      }
      if (!bucket) continue;
      byBucket.set(bucket, [...(byBucket.get(bucket) ?? []), group]);
    }
    return byBucket;
  }, [groups, packs]);

  const itemClass =
    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted";
  const bucketLabel = (b: string) => (b === "image" ? tx("图片") : tx("视频"));

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-30 cursor-default"
        aria-label={tx("关闭")}
        onClick={onClose}
      />
      <div
        className="absolute z-40 w-60 rounded-xl border border-border bg-card p-1.5 shadow-lg"
        style={{ left: x, top: y }}
      >
        <Segmented
          ariaLabel={tx("节点类型")}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
          options={[
            { value: "function", label: tx("功能") },
            { value: "io", label: tx("输入输出") },
          ]}
        />
        <div className="mt-1 max-h-72 overflow-y-auto">
          {tab === "function" ? (
            sections.size === 0 ? (
              <p className="px-2 py-3 text-xs text-muted-foreground">
                {tx("暂无分组，先到「设置 → 工作流包 → 画布分组」添加")}
              </p>
            ) : (
              <>
                {(["image", "video"] as const).map((bucket) =>
                  (sections.get(bucket) ?? []).length === 0 ? null : (
                    <div key={bucket}>
                      <div className="px-2 pb-0.5 pt-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                        {bucketLabel(bucket)}
                      </div>
                      {(sections.get(bucket) ?? []).map((g) => (
                        <button
                          key={g}
                          type="button"
                          className={itemClass}
                          onClick={() => onPick({ kind: "function", group: g })}
                        >
                          <Zap className="size-3.5 text-primary/70" />
                          {g}
                        </button>
                      ))}
                    </div>
                  ),
                )}
                <div>
                  <div className="px-2 pb-0.5 pt-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                    {tx("语音")}
                  </div>
                  {SPEECH_ITEMS.map((item) => (
                    <button
                      key={item.mode}
                      type="button"
                      className={itemClass}
                      onClick={() => onPick({ kind: "speech", speechMode: item.mode })}
                    >
                      <item.icon className="size-3.5 text-primary/70" />
                      {tx(item.label)}
                      <span className="ml-auto text-[10px] text-muted-foreground">{tx(item.hint)}</span>
                    </button>
                  ))}
                </div>
              </>
            )
          ) : (
            IO_ITEMS.map((item) => (
              <button
                key={`${item.kind}-${item.mediaKind}`}
                type="button"
                className={itemClass}
                onClick={() => onPick({ kind: item.kind, mediaKind: item.mediaKind })}
              >
                <item.icon className="size-3.5 text-primary/70" />
                {tx(item.label)}
              </button>
            ))
          )}
        </div>
      </div>
    </>
  );
}

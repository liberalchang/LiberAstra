/** 画布节点卡：输入 / 功能 / 合成。共享外壳：头部(图标+标题+状态点)+ 内容区 + 手柄。
 *
 * 交互元素带 nodrag，避免 React Flow 把点击当拖拽。
 * 结果预览点击 → 全局 lightbox；发布按钮 → publishAsset。
 */
import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  Clapperboard,
  FileText,
  FolderDown,
  Image as ImageIcon,
  Loader2,
  Mic,
  Plus,
  Video,
  Zap,
} from "lucide-react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useState } from "react";

import { api } from "@/api/client";
import type {
  ConcatNodeData,
  FunctionNodeData,
  InputNodeData,
  NodeRunStatus,
  SpeechNodeData,
} from "@/canvas/types";
import { MediaThumb } from "@/components/MediaLightbox";
import { useCanvasUiStore } from "@/components/canvas/ui-state";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";
import { useCanvasStore } from "@/stores/canvas";

export const MEDIA_ICONS = {
  image: ImageIcon,
  video: Video,
  audio: AudioLines,
  text: FileText,
} as const;

const STATUS_COLOR: Record<NodeRunStatus, string> = {
  idle: "bg-muted-foreground/40",
  pending: "bg-warning",
  running: "bg-primary",
  succeeded: "bg-success",
  failed: "bg-danger",
  canceled: "bg-muted-foreground/40",
};

const STATUS_LABEL: Record<NodeRunStatus, string> = {
  idle: "待执行",
  pending: "排队中",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  canceled: "已取消",
};

function StatusDot({ status }: { status: NodeRunStatus }) {
  const tx = useTx();
  return (
    <span
      className={cn("inline-block size-2 rounded-full", STATUS_COLOR[status])}
      title={tx(STATUS_LABEL[status])}
    />
  );
}

function NodeShell({
  icon,
  title,
  badge,
  status,
  selected,
  children,
  footer,
}: {
  icon: React.ReactNode;
  title: string;
  badge?: string;
  status: NodeRunStatus;
  selected?: boolean;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "w-[260px] rounded-xl border border-border bg-card text-card-foreground shadow-sm",
        selected && "border-primary ring-1 ring-primary/40",
      )}
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
          {icon}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{title}</span>
        {badge && (
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {badge}
          </span>
        )}
        <StatusDot status={status} />
      </div>
      <div className="px-3 py-2">{children}</div>
      {footer && <div className="border-t border-border px-3 py-2">{footer}</div>}
    </div>
  );
}

/** 结果预览区：未执行为空态；执行后显示产物缩略图 + 发布/查看操作。 */
export function ResultPreview({
  run,
  expectedKind,
}: {
  run: {
    status: NodeRunStatus;
    assetIds: number[];
    published?: boolean;
    reused?: boolean;
    error?: string | null;
  };
  expectedKind: string;
}) {
  const tx = useTx();
  const setPreview = useCanvasUiStore((s) => s.setPreview);
  const [publishing, setPublishing] = useState(false);
  const assetId = run.assetIds[0];

  if (run.status === "running" || run.status === "pending") {
    return (
      <div className="grid h-28 place-items-center rounded-lg bg-muted/40 text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }
  if (run.status === "failed") {
    return (
      <div className="grid h-28 place-items-center rounded-lg bg-danger/10 px-2 text-center text-xs text-danger">
        {run.error || tx("执行失败")}
      </div>
    );
  }
  if (!assetId) {
    return (
      <div className="grid h-28 place-items-center rounded-lg bg-muted/40 text-xs text-muted-foreground">
        {tx("尚未执行")}
      </div>
    );
  }
  const publish = async () => {
    setPublishing(true);
    try {
      await api.publishAsset(assetId);
      const store = useCanvasStore.getState();
      const node = store.nodes.find((n) => n.data.run.assetIds.includes(assetId));
      if (node) {
        store.updateNodeData(node.id, { run: { ...node.data.run, published: true } });
      }
    } finally {
      setPublishing(false);
    }
  };
  return (
    <div className="group relative">
      <button
        type="button"
        className="nodrag block h-28 w-full overflow-hidden rounded-lg"
        onClick={() => setPreview({ id: assetId, kind: expectedKind })}
      >
        <MediaThumb assetId={assetId} kind={expectedKind} className="h-28 w-full" />
      </button>
      <div className="absolute right-1.5 top-1.5 flex gap-1">
        {run.reused && (
          <span className="rounded bg-card/90 px-1.5 py-0.5 text-[10px] text-muted-foreground shadow">
            {tx("已复用")}
          </span>
        )}
        {run.published ? (
          <span className="rounded bg-success/90 px-1.5 py-0.5 text-[10px] text-white shadow">
            {tx("已保存")}
          </span>
        ) : (
          <button
            type="button"
            disabled={publishing}
            className="nodrag grid size-6 place-items-center rounded bg-card/90 text-muted-foreground shadow hover:text-primary disabled:opacity-50"
            title={tx("保存到资源库")}
            onClick={publish}
          >
            <FolderDown className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

const handleClass = "!size-2.5 !border-2 !border-card !bg-primary";

/** 右侧「+」连接钮:点击=向后快速建点(自动连线);拖动=连线(落空在末端建点)。 */
function PlusHandle({ nodeId, id }: { nodeId: string; id: string }) {
  const requestAddAfter = useCanvasUiStore((s) => s.requestAddAfter);
  const tx = useTx();
  return (
    <Handle
      type="source"
      position={Position.Right}
      id={id}
      onClick={(e) => {
        e.stopPropagation();
        requestAddAfter(nodeId);
      }}
      className="nodrag"
      style={{
        width: 20,
        height: 20,
        right: -10,
        display: "grid",
        placeItems: "center",
        background: "var(--card)",
        border: "1.5px solid var(--primary)",
        borderRadius: 9999,
        color: "var(--primary)",
        cursor: "pointer",
      }}
      title={tx("点击向后添加节点，拖动连线")}
    >
      <Plus style={{ width: 12, height: 12, pointerEvents: "none" }} />
    </Handle>
  );
}

export function InputNodeCard({ id, data, selected }: NodeProps) {
  const tx = useTx();
  const d = data as InputNodeData;
  const Icon = MEDIA_ICONS[d.mediaKind] ?? FileText;
  const setPreview = useCanvasUiStore((s) => s.setPreview);
  const titles: Record<string, string> = {
    image: tx("图片输入"),
    video: tx("视频输入"),
    audio: tx("音频输入"),
    text: tx("文本输入"),
  };
  return (
    <>
      <NodeShell
        icon={<Icon className="size-3.5" />}
        title={titles[d.mediaKind]}
        badge={d.mediaKind === "text" && d.varName ? `{{${d.varName}}}` : undefined}
        status={d.run.status}
        selected={selected}
      >
        {d.mediaKind === "text" ? (
          <p className="line-clamp-3 min-h-10 text-xs text-muted-foreground">
            {d.text || tx("在右侧属性面板输入文本…")}
          </p>
        ) : d.assetId ? (
          <button
            type="button"
            className="nodrag block h-24 w-full overflow-hidden rounded-lg"
            onClick={() => setPreview({ id: d.assetId!, kind: d.mediaKind })}
          >
            <MediaThumb assetId={d.assetId} kind={d.mediaKind} className="h-24 w-full" />
          </button>
        ) : (
          <div className="grid h-24 place-items-center rounded-lg bg-muted/40 text-xs text-muted-foreground">
            {tx("未选择文件")}
          </div>
        )}
      </NodeShell>
      <PlusHandle nodeId={id} id={`out-${id}`} />
    </>
  );
}

export function FunctionNodeCard({ id, data, selected }: NodeProps) {
  const tx = useTx();
  const d = data as FunctionNodeData;
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const { data: groups } = useQuery({
    queryKey: ["canvas-groups"],
    queryFn: api.getCanvasGroups,
    staleTime: 60_000,
  });
  const groupNames = Object.keys(groups ?? {});
  return (
    <>
      <Handle type="target" position={Position.Left} id={`in-${id}`} className={handleClass} />
      <NodeShell
        icon={<Zap className="size-3.5" />}
        title={d.pack || tx("功能节点")}
        badge={d.group || undefined}
        status={d.run.status}
        selected={selected}
        footer={
          <select
            className="nodrag w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
            value={d.group}
            onChange={(e) =>
              updateNodeData(id, { group: e.target.value, pack: "", values: {}, outputKind: null })
            }
            title={tx("所属（一批工作流包）；在右侧属性面板选择具体包")}
          >
            <option value="">{tx("选择所属…")}</option>
            {groupNames.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        }
      >
        <ResultPreview run={d.run} expectedKind={d.outputKind ?? "image"} />
        {(() => {
          const useOpt = d.promptUseOptimized && Boolean(d.promptOptimized?.trim());
          const text = useOpt ? d.promptOptimized! : d.prompt;
          if (!text) return null;
          return (
            <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground">
              {useOpt ? `✨ ${text}` : text}
            </p>
          );
        })()}
      </NodeShell>
      <PlusHandle nodeId={id} id={`out-${id}`} />
    </>
  );
}

export function ConcatNodeCard({ id, data, selected }: NodeProps) {
  const tx = useTx();
  const d = data as ConcatNodeData;
  const nodes = useCanvasStore((s) => s.nodes);
  const title = d.mediaKind === "audio" ? tx("音频合成") : tx("视频合成");
  return (
    <>
      <Handle type="target" position={Position.Left} id={`in-${id}`} className={handleClass} />
      <NodeShell
        icon={<Clapperboard className="size-3.5" />}
        title={title}
        badge={tx("合成")}
        status={d.run.status}
        selected={selected}
      >
        <ResultPreview run={d.run} expectedKind={d.mediaKind} />
        <div className="mt-1.5 flex flex-wrap gap-1">
          {d.order.length === 0 ? (
            <span className="text-xs text-muted-foreground">{tx("连接多段输入后在此排序")}</span>
          ) : (
            d.order.map((sourceId, index) => {
              const source = nodes.find((n) => n.id === sourceId);
              const label =
                source?.data.kind === "input"
                  ? tx("输入")
                  : source?.data.kind === "concat"
                    ? tx("合成")
                    : (source?.data as FunctionNodeData | undefined)?.pack || tx("节点");
              return (
                <span
                  key={sourceId}
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                >
                  {index + 1}. {label}
                </span>
              );
            })
          )}
        </div>
      </NodeShell>
      <PlusHandle nodeId={id} id={`out-${id}`} />
    </>
  );
}

export function SpeechNodeCard({ id, data, selected }: NodeProps) {
  const tx = useTx();
  const d = data as SpeechNodeData;
  const title = d.mode === "tts" ? tx("文字转语音") : tx("语音转文字");
  return (
    <>
      <Handle type="target" position={Position.Left} id={`in-${id}`} className={handleClass} />
      <NodeShell
        icon={<Mic className="size-3.5" />}
        title={title}
        badge={tx("语音")}
        status={d.run.status}
        selected={selected}
      >
        {d.mode === "tts" ? (
          <>
            <ResultPreview run={d.run} expectedKind="audio" />
            <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground">
              {d.text || tx("在右侧属性面板输入要朗读的文本…")}
            </p>
          </>
        ) : (
          <ResultPreview run={d.run} expectedKind="text" />
        )}
      </NodeShell>
      <PlusHandle nodeId={id} id={`out-${id}`} />
    </>
  );
}

export const canvasNodeTypes = {
  input: InputNodeCard,
  function: FunctionNodeCard,
  concat: ConcatNodeCard,
  speech: SpeechNodeCard,
};

/** 右侧属性面板：节点身份 → 输出变量卡 → 内容/输入槽 → 提示词 → 常用参数 → 高级参数 → 操作。
 *
 * 变量体系：每个节点都有输出变量名(默认 类型+序号,可改);功能节点的包媒体参数
 * 渲染为输入槽,下拉选择已连接节点的输出变量(bindings);提示词 / 补全支持
 * 文本变量({{名}})。登记了称呼的包插入槽位名，提交时再换成包要的写法。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Brush,
  Layers,
  Trash2,
  Clapperboard,
  FolderOpen,
  Mic,
  Play,
  Upload,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, type AssetOut, type WorkflowInputSpec, type WorkflowPackOut } from "@/api/client";
import { applyMenuToNode, providerForSpec, resolveSpec, specsForMenu, speechFieldsFromSpec, speechSpecSelected } from "@/canvas/applyMenu";
import { PresetInspector } from "@/components/canvas/PresetInspector";
import { useCanvasUiStore } from "@/components/canvas/ui-state";
import { scopeOf, validateCanvas } from "@/canvas/preflight";
import { cn } from "@/lib/utils";
import {
  nodeOutputKind,
  type CanvasFlowNode,
  type ConcatNodeData,
  type FunctionNodeData,
  type InputNodeData,
  type InputVersion,
  type MediaKind,
  type SpeechNodeData,
} from "@/canvas/types";
import { AccelControl, defaultAccelState, hasAccel, type AccelState } from "@/components/AccelControl";
import { AssetPicker } from "@/components/canvas/AssetPicker";
import { ImagePaintEditor } from "@/components/canvas/ImagePaintEditor";
import { ResultPreview } from "@/components/canvas/nodes";
import { PromptField, type PromptVar } from "@/components/PromptField";
import { CharacterInputPicker } from "@/components/canvas/CharacterInputPicker";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import { Button } from "@/components/ui/button";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { WorkflowPackControl } from "@/components/WorkflowPackHint";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { SPEECH_LANGUAGES, SpeechLanguageSelect } from "@/components/SpeechLanguageSelect";
import { useTx } from "@/i18n/tx";
import { workflowPromptPlaceholder } from "@/lib/promptPlaceholder";
import { characterPromptContext, viewLabel } from "@/lib/characterPrompt";
import { useCanvasStore } from "@/stores/canvas";

const MEDIA_TYPES = ["image", "video", "audio"] as const;

function canMergeAspect(inputs: Record<string, WorkflowInputSpec>, exclude: string[]): boolean {
  const width = inputs.width;
  const height = inputs.height;
  return (
    !!width &&
    !!height &&
    width.type !== "image" &&
    height.type !== "image" &&
    !exclude.includes("width") &&
    !exclude.includes("height")
  );
}

/** 折叠区里是否还有宽高比以外的字段。图像类型的槽位不算。 */
function hasFoldableInputs(
  inputs: Record<string, WorkflowInputSpec>,
  exclude: string[],
  hideAspect: boolean,
): boolean {
  const mergeWH = canMergeAspect(inputs, exclude);
  return Object.entries(inputs).some(([key, spec]) => {
    if (exclude.includes(key) || spec.type === "image") return false;
    if (hideAspect && mergeWH && (key === "width" || key === "height")) return false;
    return true;
  });
}

function canvasAdvancedSummary(
  tx: (text: string, vars?: Record<string, string | number>) => string,
  capability: string,
  values: Record<string, string>,
  accelOn: boolean,
  bgmPath?: string,
): string {
  if (capability === "t2i") {
    const count = values.batch_size || values.n;
    const parts = [
      values.steps ? tx("步数 {n}", { n: values.steps }) : "",
      count ? tx("{n} 张", { n: count }) : "",
      accelOn ? tx("加速已开") : "",
    ].filter(Boolean);
    return parts.join(" · ") || tx("采样与权重");
  }
  if (capability === "i2i" || capability === "upscale") {
    return accelOn ? tx("加速已开") : tx("采样与权重");
  }
  const parts = [accelOn ? tx("加速已开") : "", bgmPath ? tx("已选背景音乐") : ""].filter(Boolean);
  return parts.join(" · ") || tx("采样、配乐与权重");
}

/** 第一个启用的 ComfyUI Provider（options_from / LoRA 下拉的数据来源）。 */
function useComfyProviderId(): number | undefined {
  const { data } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders, staleTime: 60_000 });
  return data?.find((p) => p.type === "comfyui" && p.enabled)?.id;
}

/** 段落标题（10px 大写浅字,扫读定位用）。 */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
      {children}
    </div>
  );
}

/** 节点展示名（槽位下拉里带来源）。 */
function nodeTitle(node: CanvasFlowNode, tx: (s: string) => string): string {
  const d = node.data;
  if (d.kind === "function") return d.pack || tx("功能节点");
  if (d.kind === "concat") return d.mediaKind === "audio" ? tx("音频合成") : tx("视频合成");
  if (d.kind === "speech") return d.mode === "tts" ? tx("文字转语音") : tx("语音转文字");
  const titles: Record<string, string> = {
    image: tx("图片输入"),
    video: tx("视频输入"),
    audio: tx("音频输入"),
    text: tx("文本输入"),
    character: tx("角色输入"),
  };
  return titles[d.mediaKind] ?? tx("输入");
}

function sourceCaption(node: CanvasFlowNode, tx: (s: string) => string): string {
  const d = node.data;
  if (d.kind === "input") {
    if (d.characterName) return d.characterName;
    if (d.assetName) return d.assetName;
  }
  return nodeTitle(node, tx);
}

function isMaskSpec(key: string, spec: WorkflowInputSpec): boolean {
  if (key === "mask") return true;
  return (spec.label ?? "").includes("蒙版") || (spec.description ?? "").includes("蒙版");
}

/** 包登记了 mention 时，/ 列出槽位名；副标题是当前接到这个槽的上游。 */
function slotPromptVars(
  pack: WorkflowPackOut,
  bindings: Record<string, string> | undefined,
  sources: CanvasFlowNode[],
  tx: (s: string) => string,
): PromptVar[] | null {
  const slots = Object.entries(pack.inputs).filter(([key, spec]) => {
    if (spec.type !== "image" && spec.type !== "video" && spec.type !== "audio") return false;
    if (isMaskSpec(key, spec)) return false;
    return Boolean(spec.mention?.trim());
  });
  if (slots.length === 0) return null;

  const used = new Set<string>();
  const byKind: Record<string, CanvasFlowNode[]> = { image: [], video: [], audio: [] };
  for (const source of sources) {
    const kind = nodeOutputKind(source);
    if (kind === "image" || kind === "video" || kind === "audio") byKind[kind].push(source);
  }
  const cursor = { image: 0, video: 0, audio: 0 };

  return slots.map(([key, spec]) => {
    const kind = spec.type as "image" | "video" | "audio";
    const boundName = bindings?.[key] ?? "";
    let source = boundName
      ? sources.find((item) => (item.data.varName ?? "") === boundName)
      : undefined;
    if (!source) {
      const pool = byKind[kind];
      while (cursor[kind] < pool.length && used.has(pool[cursor[kind]].id)) cursor[kind] += 1;
      source = pool[cursor[kind]];
      cursor[kind] += 1;
    }
    if (source) used.add(source.id);
    return {
      name: `slot:${key}`,
      tag: spec.label?.trim() || spec.mention,
      preview: source ? sourceCaption(source, tx) : tx("未连接"),
    };
  });
}

function characterExtra(
  nodes: CanvasFlowNode[],
  edges: { source: string; target: string }[],
  nodeId: string,
  capability: string,
): string | undefined {
  const lines: string[] = [];
  const sources = edges
    .filter((edge) => edge.target === nodeId)
    .map((edge) => nodes.find((item) => item.id === edge.source))
    .filter((item): item is CanvasFlowNode => Boolean(item));
  const characters = sources.filter(
    (item) => item.data.kind === "input" && item.data.mediaKind === "character" && item.data.characterName,
  );
  for (const item of characters) {
    if (item.data.kind !== "input") continue;
    lines.push(
      characterPromptContext(
        item.data.characterName || "",
        item.data.characterDescription || "",
        item.data.characterSlot || "front",
        capability === "motion" && characters.length === 1,
      ),
    );
  }
  return lines.length ? lines.join("\n") : undefined;
}

/** 输出变量卡：变量名(可改) + 产物预览/发布 + 输入节点的直通说明。 */
function OutputVarCard({ node }: { node: CanvasFlowNode }) {
  const tx = useTx();
  const d = node.data;
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const [dup, setDup] = useState(false);

  const rename = (raw: string) => {
    const name = raw.replace(/[^\w-]/g, "");
    const others = useCanvasStore.getState().nodes.filter((n) => n.id !== node.id);
    setDup(others.some((n) => (n.data as { varName?: string }).varName === name && name !== ""));
    updateNodeData(node.id, { varName: name });
  };

  const expectedKind =
    d.kind === "input"
      ? d.mediaKind
      : d.kind === "concat"
        ? d.mediaKind
        : d.kind === "speech"
          ? d.mode === "tts"
            ? "audio"
            : "text"
          : (d.outputKind ?? "image");

  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>{tx("输出变量")}</SectionLabel>
      <Input
        value={d.varName ?? ""}
        onChange={(e) => rename(e.target.value)}
        placeholder="output_1"
        aria-label={tx("输出变量名")}
        className={dup ? "border-danger" : undefined}
      />
      {dup && <p className="text-xs text-danger">{tx("变量名与其他节点重复")}</p>}
      {d.kind === "input" && d.mediaKind === "text" ? (
        <p className="text-xs text-muted-foreground">{tx("直接传出上方输入的文本内容")}</p>
      ) : (
        <ResultPreview run={d.run} expectedKind={expectedKind} nodeId={node.id} />
      )}
    </section>
  );
}

/** 操作区:唯一的执行入口——强制执行(本节点+父链全部忽略复用重跑)。
 * 「只重跑本节点」由画布的「执行选中」承担(选中节点必真跑,上游复用)。 */
function RunActions({
  node,
  canvasId,
  onRequestSave,
  onFlash,
}: {
  node: CanvasFlowNode;
  canvasId: string;
  onRequestSave: () => Promise<boolean>;
  onFlash: (text: string, opts?: { sticky?: boolean }) => void;
}) {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  /** 预检本节点的链;不通过则红框标记 + 常驻通知,返回 false。 */
  const preflight = (): boolean => {
    const s = useCanvasStore.getState();
    const packs = queryClient.getQueryData<WorkflowPackOut[]>(["workflows"]);
    const scope = scopeOf(s.nodes, s.edges, [node.id]);
    const issues = validateCanvas(s.nodes, s.edges, packs, scope);
    if (issues.length === 0) return true;
    s.onNodesChange([{ type: "select", id: issues[0].nodeId, selected: true }]);
    useCanvasUiStore.getState().setInvalidNodes(new Set(issues.map((i) => i.nodeId)));
    onFlash(
      tx("{n} 个节点配置不完整，已用红框标出：{first}", {
        n: issues.length,
        first: issues[0].message,
      }),
      { sticky: true },
    );
    return false;
  };

  const runNode = async () => {
    if (!preflight()) return;
    if (!(await onRequestSave())) return;
    setBusy(true);
    try {
      // 后端强制本节点及整条父链(忽略指纹复用)
      await api.rerunCanvasNode(canvasId, node.id);
      useCanvasStore.getState().setRunActive(true);
    } catch (err) {
      onFlash(err instanceof Error ? err.message : tx("执行失败"), { sticky: true });
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="flex flex-col gap-1.5">
      <Button
        className="h-9 w-full"
        disabled={busy}
        onClick={() => void runNode()}
        title={tx("强制重跑此节点及其全部上游（忽略复用缓存）")}
      >
        <Play className="size-4" />
        {tx("强制执行")}
      </Button>
    </section>
  );
}

function InputInspector({ node }: { node: CanvasFlowNode }) {
  const tx = useTx();
  const d = node.data as InputNodeData;
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const fileRef = useRef<HTMLInputElement>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [converting, setConverting] = useState(false);
  const [depthError, setDepthError] = useState<string | null>(null);
  const pluginQuery = useQuery({
    queryKey: ["plugins"],
    queryFn: api.listPlugins,
    enabled: d.mediaKind === "image",
    staleTime: 30_000,
  });
  const providerQuery = useQuery({
    queryKey: ["providers"],
    queryFn: api.listProviders,
    enabled: d.mediaKind === "image",
    staleTime: 30_000,
  });
  const depthReady =
    (pluginQuery.data?.some((item) => item.id === "depth" && item.installed && item.enabled) ?? false) ||
    (providerQuery.data?.some((item) => item.type === "liber_depth" && item.enabled) ?? false);

  const applyDepth = async () => {
    if (!d.assetId || !depthReady) return;
    setConverting(true);
    setDepthError(null);
    try {
      const form = new FormData();
      form.set("asset_ids", String(d.assetId));
      const saved = await api.convertDepth(form);
      const asset = saved[0];
      if (!asset) return;
      const name = String(asset.meta?.source_name || "depth.png");
      const base = d.versions?.length
        ? d.versions
        : [{ assetId: d.assetId, label: tx("原始"), maskAssetId: d.maskAssetId ?? null }];
      updateNodeData(node.id, {
        assetId: asset.id,
        assetName: name,
        maskAssetId: null,
        versions: [
          ...base,
          { assetId: asset.id, label: `${tx("深度")} ${base.length}`, maskAssetId: null, op: "depth" },
        ],
      });
      setEditorOpen(false);
    } catch (err) {
      setDepthError(err instanceof Error ? err.message : String(err));
    } finally {
      setConverting(false);
    }
  };

  if (d.mediaKind === "text") {
    return (
      <section className="flex flex-col gap-2">
        <SectionLabel>{tx("内容")}</SectionLabel>
        <textarea
          className={`${areaClass} min-h-28 text-sm`}
          value={d.text ?? ""}
          placeholder={tx("输入文本…")}
          onChange={(e) => updateNodeData(node.id, { text: e.target.value })}
        />
      </section>
    );
  }

  if (d.mediaKind === "character") {
    return (
      <section className="flex flex-col gap-2">
        <SectionLabel>{tx("角色")}</SectionLabel>
        <button
          type="button"
          className="rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-muted/40"
          onClick={() => setPickerOpen(true)}
        >
          {d.characterName
            ? `${d.characterName} · ${tx(viewLabel(d.characterSlot || "front"))}`
            : tx("选择角色")}
        </button>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {tx("一条连线代表一个人。下游只有一个图片槽时送入镜视角；选了定妆照则送整张设定图。动作迁移默认送正面、侧面、背面。")}
        </p>
        {pickerOpen && (
          <CharacterInputPicker
            characterId={d.characterId ?? null}
            slot={d.characterSlot || "front"}
            onClose={() => setPickerOpen(false)}
            onConfirm={(picked) => {
              updateNodeData(node.id, picked);
              setPickerOpen(false);
            }}
          />
        )}
      </section>
    );
  }

  const kind = d.mediaKind as "image" | "video" | "audio";
  const accept = { image: "image/*", video: "video/*", audio: "audio/*" }[kind];

  const onUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await api.uploadFileAsAsset(file, kind);
      updateNodeData(node.id, {
        assetId: uploaded.asset_id,
        assetName: file.name,
        maskAssetId: null,
        // 换图即重开版本史:新图为唯一原始版
        versions: [{ assetId: uploaded.asset_id, label: tx("原始"), maskAssetId: null }],
      });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : tx("上传失败"));
    } finally {
      setUploading(false);
    }
  };

  const onPick = (asset: AssetOut) => {
    updateNodeData(node.id, {
      assetId: asset.id,
      assetName: String(asset.meta?.source_name ?? asset.path),
      maskAssetId: null,
      versions: [{ assetId: asset.id, label: tx("原始"), maskAssetId: null }],
    });
    setPickerOpen(false);
  };

  /** 回滚到某个版本:节点镜像(assetId/maskAssetId)跟随该版本 */
  const applyVersion = (v: InputVersion) =>
    updateNodeData(node.id, {
      assetId: v.assetId,
      maskAssetId: v.maskAssetId ?? null,
    });

  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>{tx("文件")}</SectionLabel>
      {d.assetName && (
        <p className="truncate text-xs text-muted-foreground" title={d.assetName}>
          {d.assetName}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
        >
          <Upload className="size-4" />
          {uploading ? tx("上传中…") : tx("本地上传")}
        </Button>
        <Button variant="outline" size="sm" className="flex-1" onClick={() => setPickerOpen(true)}>
          <FolderOpen className="size-4" />
          {tx("资源库")}
        </Button>
        {kind === "image" && (
          <Button
            variant="outline"
            size="sm"
            disabled={!d.assetId}
            title={tx("标记涂抹 / 蒙版 / 裁剪")}
            onClick={() => setEditorOpen(true)}
          >
            <Brush className="size-4" />
          </Button>
        )}
        {kind === "image" && (
          <Button
            variant="outline"
            size="sm"
            disabled={!d.assetId || !depthReady || converting}
            title={
              depthReady
                ? tx("转为深度图")
                : tx("请先安装并启用深度图插件，或在服务提供方启用 Liber Depth")
            }
            onClick={() => void applyDepth()}
          >
            <Layers className="size-4" />
          </Button>
        )}
      </div>
      {uploadError && <p className="text-xs text-destructive">{uploadError}</p>}
      {depthError && <p className="text-xs text-destructive">{depthError}</p>}
      {kind === "image" && d.maskAssetId && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-2 py-1.5">
          <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
            {tx("已挂蒙版(局部重绘用,白区重绘黑区保留)")}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-danger"
            title={tx("清除蒙版")}
            aria-label={tx("清除蒙版")}
            onClick={() => {
              // 摘掉当前版本的蒙版(版本史同步)
              const versions = (d.versions ?? []).map((v) =>
                v.assetId === d.assetId ? { ...v, maskAssetId: null } : v,
              );
              updateNodeData(node.id, { maskAssetId: null, versions });
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      )}
      {/* 版本史:原始 + 每次修改;点击回滚为当前版本(蒙版跟随其所属版本) */}
      {kind === "image" && (d.versions?.length ?? 0) > 1 && (
        <div className="flex flex-col gap-1">
          <span className="text-[10px] text-muted-foreground">{tx("版本(点击切换当前)")}</span>
          {(d.versions ?? []).map((v, i) => (
            <button
              key={`${v.assetId}-${i}`}
              type="button"
              onClick={() => applyVersion(v)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-2 py-1 text-left text-xs",
                v.assetId === d.assetId
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border hover:bg-muted",
              )}
            >
              <span className="min-w-0 flex-1 truncate">{v.label}</span>
              {v.maskAssetId != null && (
                <span className="shrink-0 rounded bg-accent/15 px-1 py-0.5 text-[10px] text-accent">
                  {tx("蒙版")}
                </span>
              )}
              {v.assetId === d.assetId && (
                <span className="shrink-0 text-[10px]">{tx("当前")}</span>
              )}
            </button>
          ))}
        </div>
      )}
      <input
        ref={fileRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void onUpload(file);
          e.target.value = "";
        }}
      />
      {pickerOpen && <AssetPicker kind={kind} onPick={onPick} onClose={() => setPickerOpen(false)} />}
      {editorOpen && d.assetId && (
        <ImagePaintEditor
          assetId={d.assetId}
          maskAssetId={d.maskAssetId}
          onApply={(assetId, name, op) => {
            // 修改产生新版本:原图版本保留可回滚;新版无蒙版(坐标系已变)
            const base = d.versions?.length
              ? d.versions
              : [{ assetId: d.assetId!, label: tx("原始"), maskAssetId: d.maskAssetId ?? null }];
            const label = `${op === "crop" ? tx("裁剪") : tx("涂抹")} ${base.length}`;
            updateNodeData(node.id, {
              assetId,
              assetName: name,
              maskAssetId: null,
              versions: [...base, { assetId, label, maskAssetId: null }],
            });
          }}
          onApplyMask={(assetId) => {
            // 蒙版挂到当前版本(像素对齐),节点镜像同步
            const versions = (d.versions ?? []).map((v) =>
              v.assetId === d.assetId ? { ...v, maskAssetId: assetId } : v,
            );
            updateNodeData(node.id, { maskAssetId: assetId, versions });
          }}
          depthReady={depthReady}
          onDepth={() => void applyDepth()}
          onClose={() => setEditorOpen(false)}
        />
      )}
    </section>
  );
}

/** 输入槽：包的每个媒体参数一行,下拉选择已连接节点的输出变量。 */
function InputSlots({ node, pack }: { node: CanvasFlowNode; pack: WorkflowPackOut }) {
  const tx = useTx();
  const d = node.data as FunctionNodeData;
  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);

  const mediaKeys = Object.entries(pack.inputs).filter(([, spec]) =>
    MEDIA_TYPES.includes(spec.type as (typeof MEDIA_TYPES)[number]),
  );
  if (mediaKeys.length === 0) return null;

  // 已连接的上游节点(连线顺序即默认映射顺序)
  const sources = edges
    .filter((e) => e.target === node.id)
    .map((e) => nodes.find((n) => n.id === e.source))
    .filter((n): n is CanvasFlowNode => Boolean(n));

  const kindLabel = { image: tx("图片"), video: tx("视频"), audio: tx("音频") };

  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>{tx("输入")}</SectionLabel>
      {mediaKeys.map(([key, spec]) => {
        const mediaKind = spec.type as MediaKind;
        const options = sources.filter((s) => nodeOutputKind(s) === mediaKind);
        const bound = d.bindings?.[key] ?? "";
        // 只有一个可用变量且未绑定时自动选中(与执行时的自动映射一致)
        const effective = bound || (options.length === 1 ? (options[0].data.varName ?? "") : "");
        return (
          <Field
            key={key}
            label={(spec.label ?? key) + (spec.required ? " *" : "")}
            hint={spec.description ? tx(spec.description) : undefined}
          >
            <select
              className={selectClass}
              aria-label={spec.label ?? key}
              value={effective}
              onChange={(e) =>
                updateNodeData(node.id, { bindings: { ...(d.bindings ?? {}), [key]: e.target.value } })
              }
            >
              {options.length === 0 ? (
                <option value="">
                  {tx("先连接{kind}输入", { kind: kindLabel[mediaKind as "image" | "video" | "audio"] ?? mediaKind })}
                </option>
              ) : (
                <>
                  {!bound && options.length > 1 && <option value="">{tx("自动(按连线顺序)")}</option>}
                  {options.map((s) => (
                    <option
                      key={s.id}
                      value={s.data.varName ?? ""}
                      title={nodeTitle(s, tx)}
                    >
                      {s.data.varName || s.id}
                    </option>
                  ))}
                </>
              )}
            </select>
          </Field>
        );
      })}
    </section>
  );
}

function FunctionInspector({
  node,
  canvasId,
  onRequestSave,
  onFlash,
}: {
  node: CanvasFlowNode;
  canvasId: string;
  onRequestSave: () => Promise<boolean>;
  onFlash: (text: string) => void;
}) {
  const tx = useTx();
  const d = node.data as FunctionNodeData;
  const store = useCanvasStore();
  const { data: bgmList } = useQuery({ queryKey: ["bgm"], queryFn: api.listBgm, staleTime: 60_000 });
  const providerId = useComfyProviderId();
  const { data: menu } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const { data: specs } = useQuery({ queryKey: ["execution-specs"], queryFn: () => api.executionSpecs() });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: allPacks } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.listWorkflows(),
    staleTime: 60_000,
  });
  const pack = allPacks?.find((item) => item.name === d.pack) ?? null;
  // 菜单绑包时如果还没拿到工作流列表，加速开关会丢。列表到达后补上默认值。
  useEffect(() => {
    if (!pack || !hasAccel(pack.accel) || d.accel) return;
    useCanvasStore.getState().updateNodeData(node.id, { accel: defaultAccelState(pack.accel) });
  }, [pack, d.accel, node.id]);
  const currentSpec = (specs ?? []).find(
    (row) => row.target_id === d.targetId && row.sub_capability === d.subCapability,
  );

  // 文本变量仍插 {{名}}。登记了 mention 的包按槽位名插入，其余包仍用 <Picture N>
  const variables: PromptVar[] = (() => {
    const sources = store.edges
      .filter((e) => e.target === node.id)
      .map((e) => store.nodes.find((n) => n.id === e.source))
      .filter((n): n is CanvasFlowNode => Boolean(n));
    const textVars: PromptVar[] = [];
    const mediaSources: CanvasFlowNode[] = [];
    for (const s of sources) {
      const varName = s.data.varName ?? "";
      if (!varName) continue;
      const textProducer =
        (s.data.kind === "input" && s.data.mediaKind === "text") ||
        (s.data.kind === "speech" && s.data.mode === "asr") ||
        nodeOutputKind(s) === "text";
      if (textProducer) {
        const body = s.data.kind === "input" && s.data.mediaKind === "text" ? (s.data.text ?? "") : "";
        textVars.push({
          name: varName,
          preview: body.slice(0, 40) || nodeTitle(s, tx),
          text: body,
        });
        continue;
      }
      if (nodeOutputKind(s)) mediaSources.push(s);
    }
    const slots = pack ? slotPromptVars(pack, d.bindings, sources, tx) : null;
    if (slots) return [...slots, ...textVars];
    const counters: Record<string, number> = { image: 0, video: 0, audio: 0 };
    const tagOf = (kind: string) =>
      kind === "image" ? "Picture" : kind === "video" ? "Video" : "Audio";
    const mediaVars: PromptVar[] = [];
    for (const s of mediaSources) {
      const kind = nodeOutputKind(s);
      if (!kind) continue;
      counters[kind] += 1;
      mediaVars.push({
        name: s.data.varName ?? s.id,
        tag: `<${tagOf(kind)} ${counters[kind]}>`,
        preview: sourceCaption(s, tx),
      });
    }
    return [...mediaVars, ...textVars];
  })();

  const paramExclude = [
    ...MEDIA_TYPES,
    "prompt",
    ...(pack?.capability === "avatar" || pack?.capability === "motion" ? ["length", "frames"] : []),
  ];
  const showAdvanced =
    !!pack &&
    pack.capability !== "analysis" &&
    (hasFoldableInputs(pack.inputs, paramExclude, pack.capability === "t2i") ||
      (hasAccel(pack.accel) && !!d.accel) ||
      pack.capability === "motion" ||
      pack.capability === "avatar");

  return (
    <>
      {d.presetId ? (
        <PresetInspector node={node} onFlash={onFlash} />
      ) : (
        <section className="flex flex-col gap-3">
          <SectionLabel>{tx("功能")}</SectionLabel>
          <Field label={tx("功能")} hint={tx("选中后按该功能补建还缺的输入，已有输入不会删除")}>
            <select
              className={selectClass}
              value=""
              onChange={(event) => {
                const next = (menu ?? []).find((row) => row.id === event.target.value);
                if (!next) return;
                const created = applyMenuToNode(node.id, next, resolveSpec(next, specs ?? []), providers ?? [], allPacks ?? []);
                if (created > 0) onFlash(tx("已补建 {n} 个输入节点", { n: created }));
              }}
            >
              <option value="">{tx("选择功能…")}</option>
              {(menu ?? []).map((row) => (
                <option key={row.id} value={row.id}>
                  {row.title}
                </option>
              ))}
            </select>
          </Field>
        </section>
      )}

      {pack && (
        <>
          <InputSlots node={node} pack={pack} />

          {pack.capability === "avatar" && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {tx("画面时长跟随已连接的音频。超过单段上限时按时间切开，下一段用上一段的尾帧。")}
            </p>
          )}
          {pack.capability === "motion" && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {tx("画面时长跟随参考视频。超过单段上限时分段衔接，下一张人物图用上一段的尾帧。")}
            </p>
          )}
          {pack.capability === "analysis" && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {tx("分析得到的文字写入本节点变量。下游提示词引用这个变量名。分析角度写在下方参数里。")}
            </p>
          )}

          {pack.capability !== "analysis" && (
          <PromptField
            label={tx("提示词")}
            value={{
              raw: d.prompt,
              optimized: d.promptOptimized ?? "",
              optimizedFromRaw: d.promptOptimizedFromRaw ?? "",
              useOptimized: d.promptUseOptimized ?? false,
            }}
            onChange={(v) =>
              store.updateNodeData(node.id, {
                prompt: v.raw,
                promptOptimized: v.optimized,
                promptOptimizedFromRaw: v.optimizedFromRaw,
                promptUseOptimized: v.useOptimized,
              })
            }
            variables={variables}
            jobScope={`canvas-prompt:${node.id}`}
            task={pack.capability}
            workflow={pack.name}
            placeholder={workflowPromptPlaceholder(tx, pack, { canvas: true })}
            extraContext={characterExtra(store.nodes, store.edges, node.id, pack.capability)}
            minRowsClass="min-h-20"
          />
          )}

          <section className="flex flex-col gap-3">
            {pack.capability === "analysis" ? (
              <>
                <SectionLabel>{tx("参数")}</SectionLabel>
                <WorkflowInputs
                  inputs={pack.inputs}
                  values={d.values}
                  exclude={[...MEDIA_TYPES, "prompt"]}
                  providerId={providerId}
                  fps={pack.fps}
                  singleColumn
                  onChange={(key, value) =>
                    store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
                  }
                />
              </>
            ) : (
              <>
                {pack.capability === "t2i" && canMergeAspect(pack.inputs, paramExclude) && (
                  <>
                    <SectionLabel>{tx("参数")}</SectionLabel>
                    <WorkflowInputs
                      inputs={pack.inputs}
                      values={d.values}
                      exclude={paramExclude}
                      providerId={providerId}
                      fps={pack.fps}
                      singleColumn
                      part="aspect"
                      onChange={(key, value) =>
                        store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
                      }
                    />
                  </>
                )}
                {showAdvanced && (
                  <AdvancedPanel
                    summary={canvasAdvancedSummary(
                      tx,
                      pack.capability,
                      d.values,
                      Boolean(d.accel?.enabled),
                      d.bgmPath,
                    )}
                  >
                    {hasAccel(pack.accel) && d.accel && (
                      <AccelControl
                        accel={pack.accel!}
                        providerId={providerId}
                        value={d.accel as AccelState}
                        singleColumn
                        onChange={(next) => store.updateNodeData(node.id, { accel: next })}
                        inputs={pack.inputs}
                        onApplyPreset={(patch) =>
                          store.updateNodeData(node.id, { values: { ...d.values, ...patch } })
                        }
                      />
                    )}
                    {pack.capability === "motion" && (
                      <Field
                        label={tx("声音来源")}
                        hint={tx("模型生成是画面自带的声音。参考视频原声会换成上传视频里的整条音轨。")}
                      >
                        <Segmented
                          ariaLabel={tx("声音来源")}
                          value={d.audioMode === "reference" ? "reference" : "model"}
                          onChange={(value) =>
                            store.updateNodeData(node.id, {
                              audioMode: value === "reference" ? "reference" : "model",
                            })
                          }
                          options={[
                            { value: "model", label: tx("模型生成") },
                            { value: "reference", label: tx("参考视频原声") },
                          ]}
                        />
                      </Field>
                    )}
                    {(pack.capability === "avatar" || pack.capability === "motion") && (
                      <div className="flex flex-col gap-3">
                        <Field label={tx("背景音乐")} hint={tx("可选。从音乐库选择，叠在当前声音上面。")}>
                          <select
                            className={selectClass}
                            value={(d.bgmPath ?? "").replace(/^bgm\//, "")}
                            onChange={(e) =>
                              store.updateNodeData(node.id, {
                                bgmPath: e.target.value ? `bgm/${e.target.value}` : "",
                              })
                            }
                          >
                            <option value="">{tx("无背景音乐")}</option>
                            {d.bgmPath &&
                              !bgmList?.some((item) => `bgm/${item.name}` === d.bgmPath) && (
                                <option value={d.bgmPath.replace(/^bgm\//, "")}>
                                  {d.bgmPath.replace(/^bgm\//, "")}
                                  {tx("（已不在库中）")}
                                </option>
                              )}
                            {bgmList?.map((item) => (
                              <option key={item.name} value={item.name}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <Field label={tx("BGM 音量")} hint={tx("0 到 1，建议 0.1 到 0.3。")}>
                          <Input
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            value={d.bgmVolume ?? 0.2}
                            onChange={(e) =>
                              store.updateNodeData(node.id, { bgmVolume: Number(e.target.value) || 0 })
                            }
                          />
                        </Field>
                      </div>
                    )}
                    <WorkflowInputs
                      inputs={pack.inputs}
                      values={d.values}
                      exclude={paramExclude}
                      providerId={providerId}
                      fps={pack.fps}
                      singleColumn
                      part={pack.capability === "t2i" ? "rest" : "all"}
                      onChange={(key, value) =>
                        store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
                      }
                    />
                  </AdvancedPanel>
                )}
              </>
            )}
          </section>
        </>
      )}

      {d.presetId && !pack && d.subCapability !== "analysis" && d.subCapability !== "video_analysis" && (
        <PromptField
          label={tx("提示词")}
          value={{
            raw: d.prompt,
            optimized: d.promptOptimized ?? "",
            optimizedFromRaw: d.promptOptimizedFromRaw ?? "",
            useOptimized: d.promptUseOptimized ?? false,
          }}
          onChange={(value) =>
            store.updateNodeData(node.id, {
              prompt: value.raw,
              promptOptimized: value.optimized,
              promptOptimizedFromRaw: value.optimizedFromRaw,
              promptUseOptimized: value.useOptimized,
            })
          }
          variables={variables}
          jobScope={`canvas-prompt:${node.id}`}
          task={d.subCapability || "t2i"}
          workflow={d.targetId || ""}
          placeholder={workflowPromptPlaceholder(tx, null, { canvas: true })}
          extraContext={characterExtra(store.nodes, store.edges, node.id, d.subCapability || "")}
          minRowsClass="min-h-20"
        />
      )}
      {d.presetId && !pack && currentSpec && Object.keys(currentSpec.inputs).length > 0 && (
        d.subCapability === "analysis" || d.subCapability === "video_analysis" ? (
          <section className="flex flex-col gap-3">
            <SectionLabel>{tx("参数")}</SectionLabel>
            <WorkflowInputs
              inputs={currentSpec.inputs}
              values={d.values}
              exclude={["prompt"]}
              providerId={d.providerId ?? undefined}
              singleColumn
              onChange={(key, value) =>
                store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
              }
            />
          </section>
        ) : (
          <>
            {d.subCapability === "t2i" && canMergeAspect(currentSpec.inputs, ["prompt"]) && (
              <section className="flex flex-col gap-3">
                <SectionLabel>{tx("参数")}</SectionLabel>
                <WorkflowInputs
                  inputs={currentSpec.inputs}
                  values={d.values}
                  exclude={["prompt"]}
                  providerId={d.providerId ?? undefined}
                  singleColumn
                  part="aspect"
                  onChange={(key, value) =>
                    store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
                  }
                />
              </section>
            )}
            {hasFoldableInputs(currentSpec.inputs, ["prompt"], d.subCapability === "t2i") && (
              <AdvancedPanel summary={canvasAdvancedSummary(tx, d.subCapability || "", d.values, false)}>
                <WorkflowInputs
                  inputs={currentSpec.inputs}
                  values={d.values}
                  exclude={["prompt"]}
                  providerId={d.providerId ?? undefined}
                  singleColumn
                  part={d.subCapability === "t2i" ? "rest" : "all"}
                  onChange={(key, value) =>
                    store.updateNodeData(node.id, { values: { ...d.values, [key]: value } })
                  }
                />
              </AdvancedPanel>
            )}
          </>
        )
      )}

      <RunActions node={node} canvasId={canvasId} onRequestSave={onRequestSave} onFlash={onFlash} />
    </>
  );
}

function ConcatInspector({ node }: { node: CanvasFlowNode }) {
  const tx = useTx();
  const d = node.data as ConcatNodeData;
  const nodes = useCanvasStore((s) => s.nodes);
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);

  const move = (index: number, delta: number) => {
    const order = [...d.order];
    const target = index + delta;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    updateNodeData(node.id, { order });
  };

  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>{tx("合成顺序")}</SectionLabel>
      <p className="text-xs text-muted-foreground">
        {tx("按此顺序把连接的输入拼成整段；连线时自动追加")}
      </p>
      <div className="flex flex-col gap-1">
        {d.order.length === 0 && (
          <p className="text-xs text-muted-foreground">{tx("还没有连接输入")}</p>
        )}
        {d.order.map((sourceId, index) => {
          const source = nodes.find((n) => n.id === sourceId);
          return (
            <div
              key={sourceId}
              className="flex items-center gap-2 rounded-lg border border-border px-2 py-1.5"
            >
              <span className="w-4 text-xs text-muted-foreground">{index + 1}</span>
              <span className="min-w-0 flex-1 truncate text-sm">
                {source ? `${source.data.varName || sourceId} · ${nodeTitle(source, tx)}` : sourceId}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-6"
                disabled={index === 0}
                onClick={() => move(index, -1)}
                aria-label={tx("上移")}
              >
                <ArrowUp className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-6"
                disabled={index === d.order.length - 1}
                onClick={() => move(index, 1)}
                aria-label={tx("下移")}
              >
                <ArrowDown className="size-3.5" />
              </Button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SpeechInspector({ node }: { node: CanvasFlowNode }) {
  const tx = useTx();
  const d = node.data as SpeechNodeData;
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const queryClient = useQueryClient();
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices, staleTime: 60_000 });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });

  const cap = d.mode === "tts" ? "tts" : "asr";
  const { data: menu } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const { data: specs } = useQuery({ queryKey: ["execution-specs"], queryFn: () => api.executionSpecs() });
  // 与语音页同一规则:comfy 是工作流驱动的,没有对应能力的包就不列出
  const { data: capPacks } = useQuery({
    queryKey: ["workflows", cap],
    queryFn: () => api.listWorkflows(cap),
  });
  const sameCap = (menu ?? []).filter((row) => row.enabled !== false && row.sub_capability === cap);
  const menuItem =
    (menu ?? []).find((row) => row.enabled !== false && row.id === d.presetId) ??
    (sameCap.length === 1 ? sameCap[0] : undefined);
  const pool = menuItem ? specsForMenu(menuItem, specs ?? []) : null;
  const candidates = pool
    ? (providers ?? []).filter((p) => pool.some((spec) => providerForSpec(spec, providers ?? [])?.id === p.id))
    : (providers ?? []).filter((p) => {
        if (!p.enabled || !p.capabilities.includes(cap)) return false;
        if (p.type === "comfyui") return (capPacks?.length ?? 0) > 0;
        return true;
      });
  // 未选 = 第一个可用服务(与后端 pick_provider 的默认一致)
  const provider = candidates.find((p) => p.id === d.providerId) ?? candidates[0];
  const ptype = provider?.type;
  const listed = (id: string) =>
    !pool || pool.some((spec) => spec.target_id === id && providerForSpec(spec, providers ?? [])?.id === provider?.id);
  // 菜单池用目录整行做 id，语音页下拉用短 id。有菜单时直接列池里的项，避免对不上而变成空列表。
  const menuOptions = menuItem
    ? (pool ?? []).filter((spec) => providerForSpec(spec, providers ?? [])?.id === provider?.id)
    : null;
  const menuModelSelect = menuOptions && (
    <Field
      label={tx(d.mode === "asr" ? "识别模型" : "模型 / 工作流")}
      hint={tx("来自菜单设置。手动指定时只显示勾选的项。")}
    >
      <WorkflowPackControl
        name={menuOptions.find((spec) => speechSpecSelected(spec, d) && spec.target_type === "workflow")?.target_id}
        description={
          (capPacks ?? []).find(
            (item) =>
              item.name ===
              menuOptions.find((spec) => speechSpecSelected(spec, d) && spec.target_type === "workflow")?.target_id,
          )?.description
        }
      >
      <select
        className={selectClass}
        aria-label={tx(d.mode === "asr" ? "识别模型" : "模型 / 工作流")}
        value={menuOptions.find((spec) => speechSpecSelected(spec, d))?.target_id ?? ""}
        onChange={(e) => {
          const spec = menuOptions.find((row) => row.target_id === e.target.value);
          updateNodeData(node.id, {
            presetId: menuItem?.id,
            presetTitle: menuItem?.title,
            voiceRecordId: null,
            ...speechFieldsFromSpec(spec, providers ?? []),
          });
        }}
      >
        {menuOptions.length === 0 && <option value="">{tx("菜单里还没有可用模型")}</option>}
        {menuOptions.map((spec) => (
          <option key={`${spec.target_type}:${spec.target_id}`} value={spec.target_id}>
            {spec.display_name}
          </option>
        ))}
      </select>
      </WorkflowPackControl>
    </Field>
  );
  // 菜单默认项还没写上，或当前模型已被手动指定排除时，改到允许范围内的默认项。
  useEffect(() => {
    if (!menuItem || !pool || !specs?.length) return;
    const current = d.workflow || d.voice || d.model || "";
    if (current && pool.some((spec) => speechSpecSelected(spec, d))) return;
    const chosen = resolveSpec(menuItem, specs);
    if (!chosen) return;
    updateNodeData(node.id, {
      presetId: menuItem.id,
      presetTitle: menuItem.title,
      mode: menuItem.sub_capability === "asr" ? "asr" : "tts",
      ...speechFieldsFromSpec(chosen, providers ?? []),
    });
  }, [menuItem, pool, specs, d.workflow, d.voice, d.model, providers, node.id, updateNodeData]);

  // Liber Speech 的合成包/识别模型目录(默认项 = 系统设置)
  const { data: speechCatalog } = useQuery({
    queryKey: ["speech-catalog"],
    queryFn: api.getSpeechCatalog,
    enabled: ptype === "liber_speech",
    retry: false,
  });

  // 服务音色/模型列表为空时自动拉一次(与语音页同逻辑)
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  useEffect(() => {
    if (!provider || ptype === "comfyui" || ptype === "liber_speech") return;
    if ((provider.models ?? []).length === 0 && !refreshModels.isPending) {
      refreshModels.mutate(provider.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider?.id, ptype]);

  const serviceSelect = (
    <Field label={tx("语音服务")} hint={tx("只列出已启用且具备该能力的服务;不选则用第一个可用服务。")}>
      <select
        className={selectClass}
        value={provider?.id ?? ""}
        onChange={(e) => {
          const providerId = e.target.value === "" ? null : Number(e.target.value);
          if (pool) {
            const preferred = menuItem?.default_target?.target_id;
            const spec =
              pool.find((row) => providerForSpec(row, providers ?? [])?.id === providerId && row.target_id === preferred) ??
              pool.find((row) => providerForSpec(row, providers ?? [])?.id === providerId);
            updateNodeData(node.id, {
              presetId: menuItem?.id,
              voiceRecordId: null,
              ...speechFieldsFromSpec(spec, providers ?? []),
            });
            return;
          }
          updateNodeData(node.id, {
            providerId,
            // 换服务清掉音色/模型残留,避免语言码被当成音色
            voiceRecordId: null,
            voice: "",
            model: "",
            workflow: "",
            language: "",
            format: "",
          });
        }}
      >
        {candidates.length === 0 && <option value="">{tx("没有可用服务")}</option>}
        {candidates.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </Field>
  );

  const languageSelect = (
    <Field label={tx("语言")} hint={tx("留空 = 自动识别")}>
      <select
        className={selectClass}
        value={d.language ?? ""}
        onChange={(e) => updateNodeData(node.id, { language: e.target.value })}
      >
        <option value="">{tx("自动")}</option>
        {SPEECH_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {tx(l.label)}
          </option>
        ))}
      </select>
    </Field>
  );

  if (d.mode === "asr") {
    return (
      <section className="flex flex-col gap-3">
        <SectionLabel>{tx("输入")}</SectionLabel>
        <p className="text-xs text-muted-foreground">
          {tx("连接音频或视频。转写正文写入本节点变量，下游提示词引用这个变量名。")}
        </p>
        {serviceSelect}
        {menuModelSelect || (
          <>
            {ptype === "liber_speech" && (
              <Field label={tx("识别模型")} hint={tx("不选则使用系统设置里的语音识别模型。")}>
                <select
                  className={selectClass}
                  value={d.model ?? ""}
                  onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
                >
                  <option value="">{tx("系统设置")}</option>
                  {(speechCatalog?.asr_models ?? []).filter((m) => listed(m.id)).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {ptype === "openai_stt" && (
              <Field label={tx("识别模型")} hint={tx("来自该服务的模型列表;不选则用默认。")}>
                <select
                  className={selectClass}
                  value={d.model ?? ""}
                  onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
                >
                  <option value="">{refreshModels.isPending ? tx("正在从服务拉取模型…") : tx("默认模型")}</option>
                  {(provider?.models ?? []).filter((m) => listed(m)).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </>
        )}
        {languageSelect}
        <Field label={tx("输出类型")} hint={tx("自动按 txt → json → srt → vtt 优先级输出单个文件。")}>
          <select
            className={selectClass}
            value={d.format ?? ""}
            onChange={(e) => updateNodeData(node.id, { format: e.target.value })}
          >
            <option value="">{tx("自动")}</option>
            <option value="txt">txt</option>
            <option value="json">json</option>
            <option value="srt">srt</option>
            <option value="vtt">vtt</option>
          </select>
        </Field>
      </section>
    );
  }
  return (
    <section className="flex flex-col gap-3">
      <SectionLabel>{tx("内容")}</SectionLabel>
      <Field label={tx("朗读文本")} hint={tx("支持 {{变量名}} 引用已连接的文本输入")}>
        <textarea
          className={`${areaClass} min-h-28 text-sm`}
          value={d.text ?? ""}
          placeholder={tx("输入要朗读的文本…")}
          onChange={(e) => updateNodeData(node.id, { text: e.target.value })}
        />
      </Field>
      {serviceSelect}
      {ptype === "liber_speech" && (
        <SpeechLanguageSelect
          value={d.language ?? ""}
          onChange={(value) => updateNodeData(node.id, { language: value })}
          model={(d.model || "").split(" · ")[0] || undefined}
        />
      )}
      {menuModelSelect}
      {!menuModelSelect && ptype === "liber_speech" && (
        <Field label={tx("文字转语音模型")} hint={tx("不选则使用系统设置里的文字转语音模型。")}>
          <select
            className={selectClass}
            value={d.model ?? ""}
            onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
          >
            <option value="">{tx("系统设置")}</option>
            {(speechCatalog?.tts_models ?? []).filter((m) => listed(m.id)).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </Field>
      )}
      {!menuModelSelect && ptype === "comfyui" && (
        <Field label={tx("语音工作流")} hint={tx("tts 能力的工作流包,朗读文本会自动注入。")}>
          <WorkflowPackControl
            name={d.workflow || undefined}
            description={(capPacks ?? []).find((item) => item.name === d.workflow)?.description}
          >
          <select
            className={selectClass}
            aria-label={tx("语音工作流")}
            value={d.workflow ?? ""}
            onChange={(e) => updateNodeData(node.id, { workflow: e.target.value })}
          >
            <option value="">{tx("选择语音工作流…")}</option>
            {(capPacks ?? []).filter((p) => listed(p.name)).map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          </WorkflowPackControl>
        </Field>
      )}
      {ptype && ptype !== "comfyui" && (
        <Field
          label={tx("输出格式")}
          hint={ptype === "edge_tts" ? tx("仅 mp3。本地 Edge TTS 不输出 wav / ogg。") : tx("wav / ogg 需要兼容服务支持。")}
        >
          <select
            className={selectClass}
            value={ptype === "edge_tts" ? "mp3" : d.format || "mp3"}
            disabled={ptype === "edge_tts"}
            onChange={(e) => updateNodeData(node.id, { format: e.target.value })}
          >
            <option value="mp3">mp3</option>
            {ptype !== "edge_tts" && <option value="wav">wav</option>}
            {ptype !== "edge_tts" && <option value="ogg_opus">ogg_opus</option>}
          </select>
        </Field>
      )}
      {!menuModelSelect && (ptype === "edge_tts" || ptype === "openai_tts") && (
        <Field
          label={tx("音色")}
          hint={tx("来自该服务的音色列表;为空时先点下方刷新或稍等自动拉取。")}
        >
          <select
            className={selectClass}
            value={d.voice ?? ""}
            onChange={(e) => updateNodeData(node.id, { voice: e.target.value })}
          >
            <option value="">
              {refreshModels.isPending ? tx("正在从服务拉取音色…") : tx("默认音色")}
            </option>
            {(provider?.models ?? []).filter((v) => listed(v)).map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </Field>
      )}
      {!menuModelSelect && ptype === "openai_tts" && (
        <Field label={tx("模型")} hint={tx("不选则使用该服务的默认模型 tts-1。")}>
          <Input
            value={d.model ?? ""}
            placeholder="tts-1"
            onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
          />
        </Field>
      )}
      {ptype !== "comfyui" && ptype !== "edge_tts" && ptype !== "openai_tts" && (
        <Field label={tx("音色")} hint={tx("来自音色库;不选则用配音服务的默认音色")}>
          <select
            className={selectClass}
            value={d.voiceRecordId ?? ""}
            onChange={(e) =>
              updateNodeData(node.id, {
                voiceRecordId: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          >
            <option value="">{tx("默认音色")}</option>
            {(voices ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </Field>
      )}
    </section>
  );
}

export function NodeInspector({
  node,
  canvasId,
  onRequestSave,
  onFlash,
}: {
  node: CanvasFlowNode | null;
  canvasId: string;
  onRequestSave: () => Promise<boolean>;
  onFlash: (text: string) => void;
}) {
  const tx = useTx();
  if (!node) return null;
  const titles: Record<string, string> = {
    input: tx("输入节点"),
    function: tx("功能节点"),
    concat: tx("合成节点"),
    speech: tx("语音节点"),
  };
  const icons: Record<string, React.ReactNode> = {
    input: <FolderOpen className="size-4" />,
    function: <Zap className="size-4" />,
    concat: <Clapperboard className="size-4" />,
    speech: <Mic className="size-4" />,
  };
  const statusLabel: Record<string, string> = {
    idle: "待执行",
    pending: "排队中",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    canceled: "已取消",
  };
  return (
    <aside className="absolute bottom-3 right-3 top-14 z-30 flex w-[360px] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
      {/* 头部：节点身份 + 执行状态 */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          {icons[node.data.kind]}
        </span>
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium">{titles[node.data.kind]}</h3>
        <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {tx(statusLabel[node.data.run.status] ?? node.data.run.status)}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-4">
        <OutputVarCard node={node} />
        <hr className="border-border" />
        {node.data.kind === "input" && <InputInspector node={node} />}
        {node.data.kind === "function" && (
          <FunctionInspector
            node={node}
            canvasId={canvasId}
            onRequestSave={onRequestSave}
            onFlash={onFlash}
          />
        )}
        {node.data.kind === "concat" && (
          <>
            <ConcatInspector node={node} />
            <RunActions node={node} canvasId={canvasId} onRequestSave={onRequestSave} onFlash={onFlash} />
          </>
        )}
        {node.data.kind === "speech" && (
          <>
            <SpeechInspector node={node} />
            <RunActions node={node} canvasId={canvasId} onRequestSave={onRequestSave} onFlash={onFlash} />
          </>
        )}
      </div>
    </aside>
  );
}

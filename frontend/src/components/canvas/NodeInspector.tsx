/** 右侧属性面板：节点身份 → 输出变量卡 → 内容/输入槽 → 提示词 → 参数 → 操作。
 *
 * 变量体系：每个节点都有输出变量名(默认 类型+序号,可改);功能节点的包媒体参数
 * 渲染为输入槽,下拉选择已连接节点的输出变量(bindings);提示词 / 补全支持
 * 文本变量({{名}})与媒体变量(<Picture N> 标签)。
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Brush,
  Clapperboard,
  FolderOpen,
  Mic,
  Play,
  RotateCcw,
  Upload,
  Zap,
} from "lucide-react";
import { useRef, useState } from "react";

import { api, type AssetOut, type WorkflowPackOut } from "@/api/client";
import { applyPackToNode } from "@/canvas/applyPack";
import {
  nodeOutputKind,
  type CanvasFlowNode,
  type ConcatNodeData,
  type FunctionNodeData,
  type InputNodeData,
  type MediaKind,
  type SpeechNodeData,
} from "@/canvas/types";
import { AccelControl, hasAccel, type AccelState } from "@/components/AccelControl";
import { AssetPicker } from "@/components/canvas/AssetPicker";
import { ImagePaintEditor } from "@/components/canvas/ImagePaintEditor";
import { ResultPreview } from "@/components/canvas/nodes";
import { PromptField, type PromptVar } from "@/components/PromptField";
import { Button } from "@/components/ui/button";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTx } from "@/i18n/tx";
import { useCanvasStore } from "@/stores/canvas";

const MEDIA_TYPES = ["image", "video", "audio"] as const;

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
  };
  return titles[d.mediaKind] ?? tx("输入");
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
        <ResultPreview run={d.run} expectedKind={expectedKind} />
      )}
    </section>
  );
}

/** 操作区：执行此节点(增量复用) + 强制重跑。 */
function RunActions({
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
  const [busy, setBusy] = useState(false);
  const runNode = async (force: boolean) => {
    if (!(await onRequestSave())) return;
    setBusy(true);
    try {
      if (force) await api.rerunCanvasNode(canvasId, node.id);
      else await api.runCanvas(canvasId, { node_ids: [node.id] });
      useCanvasStore.getState().setRunActive(true);
    } catch (err) {
      onFlash(err instanceof Error ? err.message : tx("执行失败"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="flex flex-col gap-1.5">
      <Button className="h-9 w-full" disabled={busy} onClick={() => void runNode(false)}>
        <Play className="size-4" />
        {tx("执行到此节点")}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="w-full text-xs text-muted-foreground"
        disabled={busy}
        onClick={() => void runNode(true)}
        title={tx("忽略上游已成功的缓存结果,整条链重新生成")}
      >
        <RotateCcw className="size-3.5" />
        {tx("强制重跑(忽略复用)")}
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

  const kind = d.mediaKind as "image" | "video" | "audio";
  const accept = { image: "image/*", video: "video/*", audio: "audio/*" }[kind];

  const onUpload = async (file: File) => {
    setUploading(true);
    try {
      const uploaded = await api.uploadFileAsAsset(file, kind);
      updateNodeData(node.id, { assetId: uploaded.asset_id, assetName: file.name });
    } finally {
      setUploading(false);
    }
  };

  const onPick = (asset: AssetOut) => {
    updateNodeData(node.id, {
      assetId: asset.id,
      assetName: String(asset.meta?.source_name ?? asset.path),
    });
    setPickerOpen(false);
  };

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
            title={tx("画笔涂抹 / 裁剪")}
            onClick={() => setEditorOpen(true)}
          >
            <Brush className="size-4" />
          </Button>
        )}
      </div>
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
          onApply={(assetId, name) => updateNodeData(node.id, { assetId, assetName: name })}
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
          <div key={key} className="flex items-center gap-2">
            <span
              className="w-20 shrink-0 truncate text-xs text-muted-foreground"
              title={spec.label ?? key}
            >
              {(spec.label ?? key) + (spec.required ? " *" : "")}
            </span>
            <select
              className={selectClass}
              style={{ height: "2rem" }}
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
                    <option key={s.id} value={s.data.varName ?? ""}>
                      {s.data.varName || s.id} · {nodeTitle(s, tx)}
                    </option>
                  ))}
                </>
              )}
            </select>
          </div>
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
  const providerId = useComfyProviderId();
  const queryClient = useQueryClient();
  const [creatingGroups, setCreatingGroups] = useState(false);

  const { data: groups } = useQuery({ queryKey: ["canvas-groups"], queryFn: api.getCanvasGroups });
  const { data: allPacks } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.listWorkflows(),
    staleTime: 60_000,
  });

  /** 按包能力(图像/视频/语音)建默认分组,建完选中第一个组。 */
  const createDefaultGroups = async () => {
    if (!allPacks) return;
    setCreatingGroups(true);
    try {
      const pick = (caps: string[]) =>
        allPacks.filter((p) => caps.includes(p.capability)).map((p) => p.name);
      const defaults: Record<string, string[]> = {};
      const image = pick(["t2i", "i2i", "upscale"]);
      const video = pick(["t2v", "i2v", "avatar", "motion"]);
      const speech = pick(["tts", "asr"]);
      if (image.length) defaults["图像"] = image;
      if (video.length) defaults["视频"] = video;
      if (speech.length) defaults["语音"] = speech;
      if (Object.keys(defaults).length === 0) {
        onFlash(tx("还没有可用的工作流包，先到「设置 → 工作流包」导入"));
        return;
      }
      await api.putCanvasGroups(defaults);
      queryClient.setQueryData(["canvas-groups"], defaults);
      store.updateNodeData(node.id, { group: Object.keys(defaults)[0] });
      onFlash(tx("已按能力建好默认分组"));
    } catch (err) {
      onFlash(err instanceof Error ? err.message : tx("创建分组失败"));
    } finally {
      setCreatingGroups(false);
    }
  };

  const groupNames = Object.keys(groups ?? {});
  const groupPacks = (groups?.[d.group] ?? [])
    .map((name) => allPacks?.find((p) => p.name === name))
    .filter((p): p is WorkflowPackOut => Boolean(p));
  const pack = groupPacks.find((p) => p.name === d.pack) ?? null;

  const applyPack = (next: WorkflowPackOut) => {
    const created = applyPackToNode(node.id, next, d.values);
    if (created > 0) onFlash(tx("已自动补建 {n} 个必填输入节点", { n: created }));
  };

  // 已连接节点的可见变量:文本变量插 {{名}},媒体变量插 <Picture N> 风格标签
  const variables: PromptVar[] = (() => {
    const sources = store.edges
      .filter((e) => e.target === node.id)
      .map((e) => store.nodes.find((n) => n.id === e.source))
      .filter((n): n is CanvasFlowNode => Boolean(n));
    const out: PromptVar[] = [];
    const counters: Record<string, number> = { image: 0, video: 0, audio: 0 };
    const tagOf = (kind: string) =>
      kind === "image" ? "Picture" : kind === "video" ? "Video" : "Audio";
    for (const s of sources) {
      const varName = s.data.varName ?? "";
      if (!varName) continue;
      if (s.data.kind === "input" && s.data.mediaKind === "text") {
        out.push({ name: varName, preview: (s.data.text ?? "").slice(0, 40) });
        continue;
      }
      const kind = nodeOutputKind(s);
      if (!kind) continue;
      counters[kind] += 1;
      out.push({
        name: varName,
        tag: `<${tagOf(kind)} ${counters[kind]}>`,
        preview: nodeTitle(s, tx),
      });
    }
    return out;
  })();

  return (
    <>
      <section className="flex flex-col gap-3">
        <SectionLabel>{tx("功能")}</SectionLabel>
        <Field label={tx("所属（一批工作流包）")}>
          <select
            className={selectClass}
            value={d.group}
            onChange={(e) =>
              store.updateNodeData(node.id, {
                group: e.target.value,
                pack: "",
                values: {},
                outputKind: null,
                accel: null,
                bindings: {},
              })
            }
          >
            <option value="">{tx("选择所属…")}</option>
            {groupNames.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </Field>

        {/* 首用死胡同化解:一个分组都没有时,一键按能力建默认分组 */}
        {groupNames.length === 0 && (
          <div className="flex flex-col gap-2 rounded-xl border border-dashed border-border bg-muted/40 p-3">
            <p className="text-xs leading-relaxed text-muted-foreground">
              {tx("画布按「所属」组织工作流包。还没有任何分组，可以按能力（图像/视频/语音）自动建好，稍后在「设置 → 工作流包」里调整。")}
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={creatingGroups}
              onClick={() => void createDefaultGroups()}
            >
              {creatingGroups ? tx("正在创建…") : tx("按能力建默认分组")}
            </Button>
          </div>
        )}

        {d.group && (
          <Field label={tx("工作流包")} hint={tx("选择后自动补全该包需要的输入节点并连线")}>
            <select
              className={selectClass}
              value={d.pack}
              onChange={(e) => {
                const next = groupPacks.find((p) => p.name === e.target.value);
                if (next) applyPack(next);
              }}
            >
              <option value="">{tx("选择工作流包…")}</option>
              {groupPacks.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
            {groupPacks.length === 0 && (
              <p className="text-xs text-warning">
                {tx("这个分组还没有工作流包，先到「设置 → 工作流包 → 画布分组」里添加")}
              </p>
            )}
          </Field>
        )}
      </section>

      {pack && (
        <>
          <InputSlots node={node} pack={pack} />

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
            minRowsClass="min-h-20"
          />

          <section className="flex flex-col gap-3">
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
          </section>
        </>
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
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices, staleTime: 60_000 });

  if (d.mode === "asr") {
    return (
      <section className="flex flex-col gap-3">
        <SectionLabel>{tx("输入")}</SectionLabel>
        <p className="text-xs text-muted-foreground">
          {tx("从「输入输出」加一个音频输入节点,连到本节点左侧;执行时取第一个连接的音频,转写为文本/字幕资产")}
        </p>
        <Field label={tx("语言")} hint={tx("留空 = 自动识别;可填 zh / en 等")}>
          <Input
            value={d.language ?? ""}
            placeholder={tx("自动")}
            onChange={(e) => updateNodeData(node.id, { language: e.target.value.trim() })}
          />
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

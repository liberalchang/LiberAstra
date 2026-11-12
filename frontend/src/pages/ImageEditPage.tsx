import { useMutation, useQuery } from "@tanstack/react-query";
import { ImageUp, WandSparkles } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { AssetPickButton } from "@/components/AssetPickButton";
import { ImagePreviewStrip } from "@/components/ImagePreviewStrip";
import {
  AccelControl,
  buildInputsWithAccel,
  defaultAccelState,
  hasAccel,
  type AccelState,
} from "@/components/AccelControl";
import { GenerateButton } from "@/components/GenerateButton";
import { PageHeader } from "@/components/PageShell";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import {
  PromptField,
  resolveEffectivePrompt,
  type PromptVar,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { submitButtonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { assetsAsFiles } from "@/lib/assets";
import { referenceImagesHint, workflowPromptPlaceholder } from "@/lib/promptPlaceholder";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { useTx } from "@/i18n/tx";

interface Props {
  /** i2i = 图生图与编辑；upscale = 修复与放大 */
  capability: "i2i" | "upscale";
  title: string;
  description: string;
}

export function ImageEditPage({ capability, title, description }: Props) {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const imageProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("image"));

  const [providerId, setProviderId] = usePersistentState<number | "">(`image-${capability}:provider`, "");
  const provider = imageProviders?.find((p) => p.id === providerId) ?? imageProviders?.[0];
  const isComfy = provider?.type === "comfyui";

  const { data: packs } = useQuery({
    queryKey: ["workflows", capability],
    queryFn: () => api.listWorkflows(capability),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = usePersistentState(`image-${capability}:workflow`, "");
  const preferredPack = capability === "upscale" ? "upscale_basic" : "";
  const pack =
    packs?.find((p) => p.name === workflow) ??
    packs?.find((p) => p.name === preferredPack) ??
    packs?.[0];
  /** 按 manifest 顺序的图像槽（含 label / required） */
  const imageInputs = pack
    ? Object.entries(pack.inputs).filter(([, spec]) => spec.type === "image")
    : [];
  const imageSlots = imageInputs.length;
  const requiredImageSlots = imageInputs.filter(([, s]) => s.required !== false).length || Math.min(1, imageSlots);
  /** 原图+蒙版包：存在名为 mask 的槽；否则按多参考图处理 */
  const isMaskPack = imageInputs.some(([key]) => key === "mask" || key.toLowerCase().includes("mask"));

  const [promptValue, setPromptValue] = usePersistentPromptValue(`image-${capability}:prompt`);
  const effectivePrompt = resolveEffectivePrompt(promptValue);
  // File 快照数组（非 FileList 活引用）：分多轮选择时追加合并，可按张删除
  const [files, setFiles] = useState<File[]>([]);
  const promptResources: PromptVar[] = files
    .slice(0, imageSlots > 0 ? imageSlots : files.length)
    .map((file, index) => {
      const [key, spec] = imageInputs[index] ?? [];
      const tag =
        spec?.mention ||
        spec?.label ||
        (isComfy ? (imageSlots === 1 ? "原图" : `image ${index + 1}`) : `参考图 ${index + 1}`);
      return {
        name: key ?? `image-${index + 1}`,
        preview: file.name,
        tag,
        kind: "image",
      };
    });
  const imageExclude = ["prompt", ...imageInputs.map(([k]) => k)];
  // 按包名分存 + 切包重载默认模型（官方/越狱互不污染）
  const [extra, setExtra] = usePersistentState<Record<string, string>>(
    `image-${capability}:extra:${pack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(pack?.inputs, imageExclude),
  );
  const [accel, setAccel] = usePersistentState<AccelState>(
    `image-${capability}:accel:${pack?.name ?? "none"}`,
    () => defaultAccelState(pack?.accel),
  );
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob(`image-${capability}`);

  const fileKey = (f: File) => `${f.name}:${f.size}:${f.lastModified}`;

  /** 追加一批文件，按 名称+大小+修改时间 去重（同一文件重复选不会重复上传） */
  const mergeFiles = (incoming: File[]) => {
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey));
      const next = [...prev];
      for (const f of incoming) {
        const k = fileKey(f);
        if (!seen.has(k)) {
          seen.add(k);
          next.push(f);
        }
      }
      return next;
    });
  };

  const addFiles = (files: File[] | null) => {
    if (!files?.length) return;
    mergeFiles(files);
  };

  const removeFile = (index: number) => setFiles((prev) => prev.filter((_, i) => i !== index));

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append("images", f);
      form.set("prompt", effectivePrompt);
      form.set("capability", capability);
      if (provider) form.set("provider_id", String(provider.id));
      if (isComfy && pack) form.set("workflow", pack.name);
      form.set("inputs", JSON.stringify(buildInputsWithAccel(extra, pack?.accel, accel)));
      return api.editImage(form);
    },
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const noPacks = isComfy && packs && packs.length === 0;
  const advancedSummary = hasAccel(pack?.accel) && accel.enabled ? tx("加速已开") : tx("采样与权重");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind={capability === "i2i" ? "edit" : "upscale"}
        icon={capability === "i2i" ? WandSparkles : ImageUp}
        title={title}
        description={description}
      />
      <SplitPane
        storageKey={`image-${capability}`}
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={tx("图像服务")} hint={tx("只列出已启用、且具备 image 能力的 Provider。")}>
              <select
                className={selectClass}
                value={provider?.id ?? ""}
                onChange={(e) => setProviderId(Number(e.target.value))}
              >
                {imageProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            {isComfy && (
              <Field label={tx("工作流包")} hint={tx("按当前能力（图生图或放大）过滤。没有对应包时先导入。")}>
                <WorkflowPackControl name={pack?.name} description={pack?.description}>
                  <PackSelect
                    packs={packs}
                    value={pack?.name ?? ""}
                    onChange={setWorkflow}
                    ariaLabel={tx("工作流包")}
                  />
                </WorkflowPackControl>
              </Field>
            )}
          </div>
          {noPacks && (
            <p className="text-sm text-muted-foreground">
              {tx("没有 {capability} 能力的工作流包，请到「设置 → 工作流包」导入。", { capability })}
            </p>
          )}
          <Field
            label={
              imageSlots <= 1
                ? tx("原图")
                : isMaskPack
                  ? tx("原图和蒙版")
                  : tx("参考图（至少 {min} 张，最多 {max} 张）", { min: requiredImageSlots, max: imageSlots })
            }
            hint={
              imageSlots <= 1
                ? tx("可多选、可分多次添加，也可以直接拖拽。传错了在下方缩略图上删除。")
                : isMaskPack
                  ? tx("按顺序添加：第 1 张是原图，第 2 张是蒙版（白色区域重画，黑色保留）。可分多次选择或拖拽，下方缩略图可单独删除。")
                  : referenceImagesHint(tx, imageInputs)
            }
          >
            <FileDrop
              accept="image/*"
              multiple
              clearAfterSelect
              title={
                imageSlots <= 1
                  ? tx("点击或拖拽上传图片")
                  : isMaskPack
                    ? tx("依次添加原图和蒙版")
                    : tx("按顺序添加参考图")
              }
              subtitle={
                imageSlots <= 1
                  ? tx("支持多选、多次添加")
                  : isMaskPack
                    ? tx("白色重画，黑色保留")
                    : tx("必选 {min} 张，可选至 {max} 张", { min: requiredImageSlots, max: imageSlots })
              }
              onSelect={addFiles}
            />
            <AssetPickButton
              kind="image"
              multiple
              onPick={async (assets) => mergeFiles(await assetsAsFiles(assets))}
            />
            <ImagePreviewStrip
              files={files}
              onRemove={removeFile}
              labelFor={(_, i) =>
                imageSlots > 1
                  ? isMaskPack
                    ? i === 0
                      ? tx("原图")
                      : i === 1
                        ? tx("蒙版")
                        : `#${i + 1}`
                    : tx(imageInputs[i]?.[1]?.label?.replace(/（.*?）/g, "") || "") || tx("图{n}", { n: i + 1 })
                  : undefined
              }
            />
          </Field>
          {(!isComfy || !pack || "prompt" in pack.inputs) && (
            <PromptField
              label={tx("提示词")}
              value={promptValue}
              onChange={setPromptValue}
              jobScope={`image-${capability}:prompt-opt`}
              task={capability === "upscale" ? "upscale" : "i2i"}
              workflow={isComfy ? pack?.name : undefined}
              resources={promptResources}
              hint={
                capability === "i2i"
                  ? tx("可输入 <Picture 1>，或按 / 插入参考图；提交时会按当前工作流包转换为实际引用名。点击 ✨ 可优化。")
                  : undefined
              }
              placeholder={workflowPromptPlaceholder(tx, isComfy ? pack : null, {
                fallback: capability === "upscale" ? "可选，用来约束画面" : "说明要怎么改",
              })}
            />
          )}
          {isComfy && pack && (
            <AdvancedPanel summary={advancedSummary}>
              {hasAccel(pack.accel) && pack.accel && (
                <AccelControl
                  accel={pack.accel}
                  providerId={provider?.id}
                  value={accel}
                  onChange={setAccel}
                  inputs={pack.inputs}
                  onApplyPreset={(patch) => setExtra((prev) => ({ ...prev, ...patch }))}
                />
              )}
              <WorkflowInputs
                inputs={pack.inputs}
                values={extra}
                onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
                exclude={imageExclude}
                providerId={provider?.id}
              />
            </AdvancedPanel>
          )}
        </CardContent>
      </Card>
        }
        footer={
          <div className="flex flex-col gap-2">
            {error && <p className="text-sm text-danger">{error}</p>}
            {imageSlots > 1 && files.length > 0 && files.length < requiredImageSlots && (
              <p className="text-sm text-muted-foreground">
                {isMaskPack
                  ? tx("此工作流需要 {need} 张图（原图 + 蒙版），还差 {left} 张", {
                      need: requiredImageSlots,
                      left: requiredImageSlots - files.length,
                    })
                  : tx("至少上传 {need} 张参考图，还差 {left} 张", {
                      need: requiredImageSlots,
                      left: requiredImageSlots - files.length,
                    })}
              </p>
            )}
            <GenerateButton
              className={submitButtonClass}
              running={!!running}
              jobId={job?.id}
              progress={job?.progress}
              disabled={
                files.length < Math.max(requiredImageSlots, 1) ||
                files.length > Math.max(imageSlots, 1) ||
                (isComfy && !pack) ||
                submit.isPending
              }
              onGenerate={() => submit.mutate()}
              label={tx("开始")}
            />
          </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="image"
            historyKind="image"
            jobFunction={capability === "upscale" ? "image.upscale" : "image.i2i,image.edit"}
            emptyHint={tx("上传原图后开始处理")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              { label: tx("工作流"), value: isComfy ? (pack?.name ?? "") : "" },
              {
                label: promptValue.useOptimized && promptValue.optimized.trim() ? tx("提示词（已优化）") : tx("提示词"),
                value: effectivePrompt,
              },
            ]}
          />
        }
      />
    </div>
  );
}

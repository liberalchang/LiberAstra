import { useMutation, useQuery } from "@tanstack/react-query";
import { ImageUp, WandSparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import {
  PromptField,
  emptyPromptValue,
  resolveEffectivePrompt,
  type PromptFieldValue,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";

interface Props {
  /** i2i = 图生图与编辑；upscale = 修复与放大 */
  capability: "i2i" | "upscale";
  title: string;
  description: string;
}

export function ImageEditPage({ capability, title, description }: Props) {
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
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];
  /** 按 manifest 顺序的图像槽（含 label / required） */
  const imageInputs = pack
    ? Object.entries(pack.inputs).filter(([, spec]) => spec.type === "image")
    : [];
  const imageSlots = imageInputs.length;
  const requiredImageSlots = imageInputs.filter(([, s]) => s.required !== false).length || Math.min(1, imageSlots);
  /** 原图+蒙版包：存在名为 mask 的槽；否则按多参考图处理 */
  const isMaskPack = imageInputs.some(([key]) => key === "mask" || key.toLowerCase().includes("mask"));

  const [legacyPrompt, setLegacyPrompt] = usePersistentState(`image-${capability}:prompt`, "");
  const [promptValue, setPromptValue] = useState<PromptFieldValue>(() => emptyPromptValue(legacyPrompt));
  const effectivePrompt = resolveEffectivePrompt(promptValue);
  // File 快照数组（非 FileList 活引用）：分多轮选择时追加合并，可按张删除
  const [files, setFiles] = useState<File[]>([]);
  const [extra, setExtra] = usePersistentState<Record<string, string>>(`image-${capability}:extra`, {});
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob(`image-${capability}`);

  const fileKey = (f: File) => `${f.name}:${f.size}:${f.lastModified}`;

  /** 追加本轮选择，按 名称+大小+修改时间 去重（同一文件重复选不会重复上传） */
  const addFiles = (list: FileList | null) => {
    if (!list?.length) return;
    // 必须同步快照：FileList 是活引用，onChange 随后清空 input.value 会把它掏空，
    // 而 setFiles 的 updater 可能被 React 延迟执行（届时再读就什么都拿不到）
    const incoming = Array.from(list);
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

  const removeFile = (index: number) => setFiles((prev) => prev.filter((_, i) => i !== index));

  // 缩略图预览 URL，随 files 变化重建并释放旧的
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append("images", f);
      form.set("prompt", effectivePrompt);
      if (provider) form.set("provider_id", String(provider.id));
      if (isComfy && pack) form.set("workflow", pack.name);
      form.set(
        "inputs",
        JSON.stringify(Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== ""))),
      );
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
            <Field label="图像服务" hint="只列出已启用、且具备 image 能力的 Provider。">
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
              <Field label="工作流包" hint="按当前能力（图生图或放大）过滤。没有对应包时先导入。">
                <select
                  className={selectClass}
                  value={pack?.name ?? ""}
                  onChange={(e) => setWorkflow(e.target.value)}
                >
                  {packs?.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>
          {noPacks && (
            <p className="text-sm text-muted-foreground">
              没有 {capability} 能力的工作流包，请到「设置 → 工作流包」导入。
            </p>
          )}
          <Field
            label={
              imageSlots <= 1
                ? "原图"
                : isMaskPack
                  ? "原图和蒙版"
                  : `参考图（至少 ${requiredImageSlots} 张，最多 ${imageSlots} 张）`
            }
            hint={
              imageSlots <= 1
                ? "可多选、可分多次添加，也可以直接拖拽。传错了在下方缩略图上删除。"
                : isMaskPack
                  ? "按顺序添加：第 1 张是原图，第 2 张是蒙版（白色区域重画，黑色保留）。可分多次选择或拖拽，下方缩略图可单独删除。"
                  : "按顺序对应 image 1、image 2…。第 1 张为主图/画布，其余为参考。提示词里用「image 1」「image 2」指代。可分多次添加。"
            }
          >
            <FileDrop
              accept="image/*"
              multiple
              clearAfterSelect
              title={
                imageSlots <= 1
                  ? "点击或拖拽上传图片"
                  : isMaskPack
                    ? "依次添加原图和蒙版"
                    : "按顺序添加参考图"
              }
              subtitle={
                imageSlots <= 1
                  ? "支持多选、多次添加"
                  : isMaskPack
                    ? "白色重画，黑色保留"
                    : `必选 ${requiredImageSlots} 张，可选至 ${imageSlots} 张`
              }
              onSelect={addFiles}
            />
            {files.length > 0 && (
              <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                {files.map((f, i) => (
                  <div
                    key={fileKey(f)}
                    className="group relative size-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted"
                  >
                    <img src={previews[i]} alt={f.name} className="size-full object-cover" />
                    {imageSlots > 1 && (
                      <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[10px] leading-none text-white">
                        {isMaskPack
                          ? i === 0
                            ? "原图"
                            : i === 1
                              ? "蒙版"
                              : `#${i + 1}`
                          : imageInputs[i]?.[1]?.label?.replace(/（.*?）/g, "") || `图${i + 1}`}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      title={`移除 ${f.name}`}
                      className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-red-500 group-hover:opacity-100"
                    >
                      <X className="size-3" />
                    </button>
                    <span className="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-[10px] leading-none text-white">
                      {f.name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Field>
          <PromptField
            label="提示词"
            hint={
              imageSlots > 1
                ? "只写白色区域里要变成什么，并写明脸、姿势等要保持的部分。"
                : capability === "i2i"
                  ? "说明要怎么改，例如把背景换成海滩。"
                  : "放大或修复时可选，用来约束画面。"
            }
            value={promptValue}
            onChange={(v) => {
              setPromptValue(v);
              setLegacyPrompt(v.raw);
            }}
            task={capability === "upscale" ? "upscale" : "i2i"}
            workflow={isComfy ? pack?.name : undefined}
            placeholder={
              isMaskPack
                ? "例如：把涂白的衣服换成淡紫色连衣裙，保持人脸和姿势"
                : imageSlots > 1
                  ? "例如：将 image 1 中的女性和 image 2 中的男性合成同一张合影，统一光照"
                  : capability === "i2i"
                    ? "例如：把背景换成海滩"
                    : "可选"
            }
          />
          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={["prompt", ...imageInputs.map(([k]) => k)]}
              providerId={provider?.id}
            />
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={
                files.length < Math.max(requiredImageSlots, 1) ||
                files.length > Math.max(imageSlots, 1) ||
                (isComfy && !pack) ||
                submit.isPending ||
                !!running
              }
            >
              {running ? `处理中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始"}
            </Button>
            {imageSlots > 1 && files.length > 0 && files.length < requiredImageSlots && (
              <span className="text-sm text-muted-foreground">
                {isMaskPack
                  ? `此工作流需要 ${requiredImageSlots} 张图（原图 + 蒙版），还差 ${requiredImageSlots - files.length} 张`
                  : `至少上传 ${requiredImageSlots} 张参考图，还差 ${requiredImageSlots - files.length} 张`}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="image"
            historyKind="image"
            emptyHint="上传原图后开始处理"
            meta={[
              { label: "服务", value: provider?.name ?? "" },
              { label: "工作流", value: isComfy ? (pack?.name ?? "") : "" },
              {
                label: promptValue.useOptimized && promptValue.optimized.trim() ? "提示词（已优化）" : "提示词",
                value: effectivePrompt,
              },
            ]}
          />
        }
      />
    </div>
  );
}

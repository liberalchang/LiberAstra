import { useMutation, useQuery } from "@tanstack/react-query";
import { ImageUp, WandSparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/api/client";
import {
  AccelControl,
  buildInputsWithAccel,
  defaultAccelState,
  hasAccel,
  type AccelState,
} from "@/components/AccelControl";
import { PageHeader } from "@/components/PageShell";
import {
  PromptField,
  resolveEffectivePrompt,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
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
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];
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
                  : tx("按顺序对应 image 1、image 2…。第 1 张为主图/画布，其余为参考。提示词里用「image 1」「image 2」指代。可分多次添加。")
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
                            ? tx("原图")
                            : i === 1
                              ? tx("蒙版")
                              : `#${i + 1}`
                          : tx(imageInputs[i]?.[1]?.label?.replace(/（.*?）/g, "") || "") || tx("图{n}", { n: i + 1 })}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      title={tx("移除 {name}", { name: f.name })}
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
            label={tx("提示词")}
            hint={
              imageSlots > 1
                ? tx("只写白色区域里要变成什么，并写明脸、姿势等要保持的部分。")
                : capability === "i2i"
                  ? tx("说明要怎么改，例如把背景换成海滩。")
                  : tx("放大或修复时可选，用来约束画面。")
            }
            value={promptValue}
            onChange={setPromptValue}
            jobScope={`image-${capability}:prompt-opt`}
            task={capability === "upscale" ? "upscale" : "i2i"}
            workflow={isComfy ? pack?.name : undefined}
            placeholder={
              isMaskPack
                ? tx("例如：把涂白的衣服换成淡紫色连衣裙，保持人脸和姿势")
                : imageSlots > 1
                  ? tx("例如：将 image 1 中的女性和 image 2 中的男性合成同一张合影，统一光照")
                  : capability === "i2i"
                    ? tx("例如：把背景换成海滩")
                    : tx("可选")
            }
          />
          {isComfy && pack && hasAccel(pack.accel) && pack.accel && (
            <AccelControl
              accel={pack.accel}
              providerId={provider?.id}
              value={accel}
              onChange={setAccel}
            />
          )}
          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={imageExclude}
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
              {running ? tx("处理中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始")}
            </Button>
            {imageSlots > 1 && files.length > 0 && files.length < requiredImageSlots && (
              <span className="text-sm text-muted-foreground">
                {isMaskPack
                  ? tx("此工作流需要 {need} 张图（原图 + 蒙版），还差 {left} 张", {
                      need: requiredImageSlots,
                      left: requiredImageSlots - files.length,
                    })
                  : tx("至少上传 {need} 张参考图，还差 {left} 张", {
                      need: requiredImageSlots,
                      left: requiredImageSlots - files.length,
                    })}
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

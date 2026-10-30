import { useMutation, useQuery } from "@tanstack/react-query";
import { Dices, ImagePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/api/client";
import { enabledModels } from "@/lib/modelCatalog";
import {
  AccelControl,
  buildInputsWithAccel,
  defaultAccelState,
  hasAccel,
  type AccelState,
} from "@/components/AccelControl";
import { PageHeader } from "@/components/PageShell";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import {
  PromptField,
  emptyPromptValue,
  resolveEffectivePrompt,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { ASPECT_OPTIONS, AspectSelect, CUSTOM_RATIO, type AspectOption } from "@/components/ui/aspect-select";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { useTx } from "@/i18n/tx";

const DEDICATED = ["prompt", "negative_prompt", "width", "height", "steps", "seed", "batch_size"];

export function ImageGenPage() {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const imageProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("image"));

  const [providerId, setProviderId] = usePersistentState<number | "">("image-generate:provider", "");
  const provider = imageProviders?.find((p) => p.id === providerId) ?? imageProviders?.[0];
  const isComfy = provider?.type === "comfyui";
  const isArk = provider?.type === "volcengine_ark";
  const arkModels = enabledModels(provider, "t2i");
  const [arkModel, setArkModel] = usePersistentState("image-generate:ark-model", "");
  const selectedArk = arkModels.find((item) => item.id === arkModel) ?? arkModels[0];
  const { data: arkSpecs } = useQuery({
    queryKey: ["execution-specs", "t2i"],
    queryFn: () => api.executionSpecs("t2i"),
    enabled: isArk,
  });
  const arkSpec = arkSpecs?.find((spec) => spec.target_id === selectedArk?.id && spec.target_type === "model");
  const [arkExtra, setArkExtra] = usePersistentState<Record<string, string>>(
    `image-generate:ark-extra:${selectedArk?.id ?? "none"}`,
    {},
  );

  const { data: packs } = useQuery({
    queryKey: ["workflows", "t2i"],
    queryFn: () => api.listWorkflows("t2i"),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = usePersistentState("image-generate:workflow", "");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const location = useLocation();
  const incomingPrompt = (location.state as { prompt?: string } | null)?.prompt;
  const [promptValue, setPromptValue] = usePersistentPromptValue("image-generate:prompt");
  useEffect(() => {
    if (incomingPrompt) {
      setPromptValue(emptyPromptValue(incomingPrompt));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const effectivePrompt = resolveEffectivePrompt(promptValue);
  const [negative, setNegative] = usePersistentState("image-generate:negative", "");
  const [aspectRaw, setAspect] = usePersistentState<AspectOption>("image-generate:aspect", ASPECT_OPTIONS[1]);
  const validCustom =
    aspectRaw &&
    Number.isFinite(aspectRaw.width) &&
    Number.isFinite(aspectRaw.height) &&
    aspectRaw.width >= 64 &&
    aspectRaw.height >= 64;
  const aspect =
    aspectRaw?.ratio === CUSTOM_RATIO && validCustom
      ? { ratio: CUSTOM_RATIO, width: Math.round(aspectRaw.width), height: Math.round(aspectRaw.height) }
      : (ASPECT_OPTIONS.find((o) => o.width === aspectRaw?.width && o.height === aspectRaw?.height) ??
        ASPECT_OPTIONS[1]);
  const [steps, setSteps] = usePersistentState("image-generate:steps", 20);
  const [seed, setSeed] = usePersistentState("image-generate:seed", -1);
  const [count, setCount] = usePersistentState("image-generate:count", 1);
  // 按包名分存 + key 切换时重载：无存档则用该包 options_from 默认（如 UC UNET）
  const [extra, setExtra] = usePersistentState<Record<string, string>>(
    `image-generate:extra:${pack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(pack?.inputs, DEDICATED),
  );
  const [accel, setAccel] = usePersistentState<AccelState>(
    `image-generate:accel:${pack?.name ?? "none"}`,
    () => defaultAccelState(pack?.accel),
  );
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("image-generate");

  const submit = useMutation({
    mutationFn: () =>
      api.generateImage({
        provider_id: provider?.id,
        workflow: isComfy ? pack?.name : undefined,
        model: isArk ? selectedArk?.id : undefined,
        options: isArk ? arkExtra : undefined,
        prompt: effectivePrompt,
        negative_prompt: negative,
        width: aspect.width,
        height: aspect.height,
        steps,
        seed,
        n: count,
        inputs: buildInputsWithAccel(extra, pack?.accel, accel) as Record<string, unknown>,
      }),
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const advancedSummary = [
    tx("步数 {n}", { n: steps }),
    tx("{n} 张", { n: count }),
    hasAccel(pack?.accel) && accel.enabled ? tx("加速已开") : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="image"
        icon={ImagePlus}
        title={tx("文生图")}
        description={tx("选择图像服务，用提示词生成图片。ComfyUI 工作流会带出额外参数。")}
      />
      <SplitPane
        storageKey="image-generate"
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
            {isArk && (
              <Field label={tx("模型")} hint={tx("只列出已启用、且支持文生图的模型。")}>
                <select className={selectClass} value={selectedArk?.id ?? ""} onChange={(e) => setArkModel(e.target.value)}>
                  {arkModels.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
              </Field>
            )}
            {isComfy && (
              <Field label={tx("工作流包")} hint={tx("ComfyUI 使用这个包里的参数。没有包时先到工作流包页面导入。")}>
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

          <PromptField
            value={promptValue}
            onChange={setPromptValue}
            jobScope="image-generate:prompt-opt"
            task="t2i"
            workflow={isComfy ? pack?.name : undefined}
            aspect={aspect.ratio}
            extraContext={
              !isComfy && provider
                ? tx("图像服务：{name}（type={type}）。按该服务常见自然语言提示词风格扩写。", {
                    name: provider.name,
                    type: provider.type,
                  })
                : undefined
            }
            placeholder={tx("例如：窗边的陶瓷杯，柔和侧光，浅景深")}
          />
          <AspectSelect value={aspect} onChange={setAspect} />
          <AdvancedPanel summary={advancedSummary}>
            <Field label={tx("负面提示词")} hint={tx("不希望出现的内容，可以留空。")}>
              <Input
                placeholder={tx("例如：模糊，变形，多余手指")}
                value={negative}
                onChange={(e) => setNegative(e.target.value)}
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label={tx("步数")} hint={tx("采样步数，1 到 150。数值越大通常越慢。")}>
                <NumberStepper
                  ariaLabel={tx("步数")}
                  min={1}
                  max={150}
                  value={steps}
                  onChange={setSteps}
                />
              </Field>
              <Field label={tx("种子")} hint={tx("-1 表示每次随机，也可以用右侧按钮摇一个。")}>
                <div className="flex gap-2">
                  <div className="min-w-0 flex-1">
                    <NumberStepper
                      ariaLabel={tx("种子")}
                      min={-1}
                      max={2147483647}
                      value={seed}
                      onChange={setSeed}
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    title={tx("随机一个种子")}
                    onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                  >
                    <Dices />
                  </Button>
                </div>
              </Field>
              <Field label={tx("张数")} hint={tx("同一次生成的张数，1 到 4。ComfyUI 用连续种子各出一张。")}>
                <NumberStepper
                  ariaLabel={tx("张数")}
                  min={1}
                  max={4}
                  value={count}
                  onChange={setCount}
                />
              </Field>
            </div>
            {isComfy && pack && hasAccel(pack.accel) && pack.accel && (
              <AccelControl
                accel={pack.accel}
                providerId={provider?.id}
                value={accel}
                onChange={setAccel}
                inputs={pack.inputs}
                onApplyPreset={(patch) => setExtra((prev) => ({ ...prev, ...patch }))}
              />
            )}
            {isArk && arkSpec && (
              <WorkflowInputs
                inputs={arkSpec.inputs}
                values={arkExtra}
                onChange={(key, value) => setArkExtra((current) => ({ ...current, [key]: value }))}
                exclude={["prompt"]}
              />
            )}
            {isComfy && pack && (
              <WorkflowInputs
                inputs={pack.inputs}
                values={extra}
                onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
                exclude={DEDICATED}
                providerId={provider?.id}
              />
            )}
          </AdvancedPanel>
        </CardContent>
      </Card>
        }
        footer={
          <div className="flex flex-col gap-2">
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className={submitButtonClass} onClick={() => submit.mutate()} disabled={!effectivePrompt || submit.isPending || !!running}>
              {running ? tx("生成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("生成")}
            </Button>
          </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="image"
            historyKind="image"
            emptyHint={tx("填写左侧参数，生成第一张图片")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              { label: tx("工作流"), value: isComfy ? (pack?.name ?? "") : "" },
              { label: tx("尺寸"), value: `${aspect.width}×${aspect.height}` },
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

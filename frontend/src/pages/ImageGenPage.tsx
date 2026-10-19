import { useMutation, useQuery } from "@tanstack/react-query";
import { Image as ImageIcon, Dices } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import {
  PromptField,
  emptyPromptValue,
  resolveEffectivePrompt,
  type PromptFieldValue,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { ASPECT_OPTIONS, AspectSelect, CUSTOM_RATIO, type AspectOption } from "@/components/ui/aspect-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";

const DEDICATED = ["prompt", "negative_prompt", "width", "height", "steps", "seed", "batch_size"];

export function ImageGenPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const imageProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("image"));

  const [providerId, setProviderId] = usePersistentState<number | "">("image-generate:provider", "");
  const provider = imageProviders?.find((p) => p.id === providerId) ?? imageProviders?.[0];
  const isComfy = provider?.type === "comfyui";

  const { data: packs } = useQuery({
    queryKey: ["workflows", "t2i"],
    queryFn: () => api.listWorkflows("t2i"),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = usePersistentState("image-generate:workflow", "");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const location = useLocation();
  const incomingPrompt = (location.state as { prompt?: string } | null)?.prompt;
  const [legacyPrompt, setLegacyPrompt] = usePersistentState("image-generate:prompt", "");
  const [promptValue, setPromptValue] = useState<PromptFieldValue>(() => emptyPromptValue(legacyPrompt));
  useEffect(() => {
    if (incomingPrompt) {
      setPromptValue(emptyPromptValue(incomingPrompt));
      setLegacyPrompt(incomingPrompt);
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
  const [extra, setExtra] = usePersistentState<Record<string, string>>("image-generate:extra", {});
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("image-generate");

  const submit = useMutation({
    mutationFn: () =>
      api.generateImage({
        provider_id: provider?.id,
        workflow: isComfy ? pack?.name : undefined,
        prompt: effectivePrompt,
        negative_prompt: negative,
        width: aspect.width,
        height: aspect.height,
        steps,
        seed,
        n: count,
        inputs: Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== "")),
      }),
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="image"
        icon={ImageIcon}
        title="文生图"
        description="选择图像服务，用提示词生成图片。ComfyUI 工作流会带出额外参数。"
      />
      <SplitPane
        storageKey="image-generate"
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
              <Field label="工作流包" hint="ComfyUI 使用这个包里的参数。没有包时先到工作流包页面导入。">
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

          <PromptField
            value={promptValue}
            onChange={(v) => {
              setPromptValue(v);
              setLegacyPrompt(v.raw);
            }}
            task="t2i"
            workflow={isComfy ? pack?.name : undefined}
            aspect={aspect.ratio}
            extraContext={
              !isComfy && provider
                ? `图像服务：${provider.name}（type=${provider.type}）。按该服务常见自然语言提示词风格扩写。`
                : undefined
            }
            placeholder="例如：窗边的陶瓷杯，柔和侧光，浅景深"
          />
          <Field label="负面提示词" hint="不希望出现的内容，可以留空。">
            <Input
              placeholder="例如：模糊，变形，多余手指"
              value={negative}
              onChange={(e) => setNegative(e.target.value)}
            />
          </Field>
          <AspectSelect value={aspect} onChange={setAspect} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="步数" hint="采样步数，1 到 150。数值越大通常越慢。">
              <NumberStepper
                ariaLabel="步数"
                min={1}
                max={150}
                value={steps}
                onChange={setSteps}
              />
            </Field>
            <Field label="种子" hint="-1 表示每次随机，也可以用右侧按钮摇一个。">
              <div className="flex gap-2">
                <div className="min-w-0 flex-1">
                  <NumberStepper
                    ariaLabel="种子"
                    min={-1}
                    max={2147483647}
                    value={seed}
                    onChange={setSeed}
                  />
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  title="随机一个种子"
                  onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                >
                  <Dices />
                </Button>
              </div>
            </Field>
            <Field label="张数" hint="同一次生成的张数，1 到 4。ComfyUI 用连续种子各出一张。">
              <NumberStepper
                ariaLabel="张数"
                min={1}
                max={4}
                value={count}
                onChange={setCount}
              />
            </Field>
          </div>

          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={DEDICATED}
              providerId={provider?.id}
            />
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!effectivePrompt || submit.isPending || !!running}>
              {running ? `生成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "生成"}
            </Button>
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="image"
            historyKind="image"
            emptyHint="填写左侧参数，生成第一张图片"
            meta={[
              { label: "服务", value: provider?.name ?? "" },
              { label: "工作流", value: isComfy ? (pack?.name ?? "") : "" },
              { label: "尺寸", value: `${aspect.width}×${aspect.height}` },
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

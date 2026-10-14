import { useMutation, useQuery } from "@tanstack/react-query";
import { Image as ImageIcon, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { ASPECT_OPTIONS, AspectSelect, type AspectOption } from "@/components/ui/aspect-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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
  const [prompt, setPrompt] = usePersistentState("image-generate:prompt", "");
  // 从其他页面带过来的提示词优先于本地记忆
  useEffect(() => {
    if (incomingPrompt) setPrompt(incomingPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [negative, setNegative] = usePersistentState("image-generate:negative", "");
  const [aspectRaw, setAspect] = usePersistentState<AspectOption>("image-generate:aspect", ASPECT_OPTIONS[1]);
  // 持久化的宽高比需对回当前选项表，失效时回落默认 1:1 1024×1024
  const aspect =
    ASPECT_OPTIONS.find((o) => o.width === aspectRaw?.width && o.height === aspectRaw?.height) ??
    ASPECT_OPTIONS[1];
  const [steps, setSteps] = usePersistentState("image-generate:steps", 20);
  const [seed, setSeed] = usePersistentState("image-generate:seed", -1);
  const [count, setCount] = usePersistentState("image-generate:count", 1);
  const [extra, setExtra] = usePersistentState<Record<string, string>>("image-generate:extra", {});
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("image-generate");

  const optimize = useMutation({
    mutationFn: () => api.optimizePrompt(prompt),
    onSuccess: (r) => setPrompt(r.optimized),
    onError: (err) => setError(err.message),
  });

  const submit = useMutation({
    mutationFn: () =>
      api.generateImage({
        provider_id: provider?.id,
        workflow: isComfy ? pack?.name : undefined,
        prompt,
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

          <Field label="提示词" hint="描述画面。右侧按钮会调用已配置的 LLM 改写这段文字。">
            <div className="flex gap-2">
              <textarea
                className={`${areaClass} min-h-24 flex-1`}
                placeholder="例如：窗边的陶瓷杯，柔和侧光，浅景深"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
              <Button
                variant="outline"
                size="icon"
                title="用 LLM 优化提示词"
                onClick={() => optimize.mutate()}
                disabled={!prompt || optimize.isPending}
              >
                <Sparkles />
              </Button>
            </div>
          </Field>
          <Field label="负面提示词" hint="不希望出现的内容，可以留空。">
            <Input
              placeholder="例如：模糊，变形，多余手指"
              value={negative}
              onChange={(e) => setNegative(e.target.value)}
            />
          </Field>
          <AspectSelect value={aspect} onChange={setAspect} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="步数" hint="采样步数。数值越大通常越慢。">
              <Input type="number" value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
            </Field>
            <Field label="种子" hint="-1 表示每次随机。">
              <Input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
            </Field>
            <Field label="张数" hint="同一次生成的张数，1 到 4。ComfyUI 用连续种子各出一张。">
              <Input
                type="number"
                min={1}
                max={4}
                value={count}
                onChange={(e) => setCount(Math.min(4, Math.max(1, Number(e.target.value) || 1)))}
              />
            </Field>
          </div>

          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={DEDICATED}
            />
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!prompt || submit.isPending || !!running}>
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
              { label: "提示词", value: prompt },
            ]}
          />
        }
      />
    </div>
  );
}

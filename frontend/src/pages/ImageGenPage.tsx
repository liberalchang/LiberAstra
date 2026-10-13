import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useJob } from "@/hooks/useJob";

const DEDICATED = ["prompt", "negative_prompt", "width", "height", "steps", "seed"];

export function ImageGenPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const imageProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("image"));

  const [providerId, setProviderId] = useState<number | "">("");
  const provider = imageProviders?.find((p) => p.id === providerId) ?? imageProviders?.[0];
  const isComfy = provider?.type === "comfyui";

  const { data: packs } = useQuery({
    queryKey: ["workflows", "t2i"],
    queryFn: () => api.listWorkflows("t2i"),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = useState("");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [steps, setSteps] = useState(20);
  const [seed, setSeed] = useState(-1);
  const [extra, setExtra] = useState<Record<string, string>>({});
  const [jobId, setJobId] = useState<string | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId).data;

  useEffect(() => {
    if (job?.status === "failed") setError(job.error ?? "任务失败");
    if (job?.status !== "succeeded") return;
    Promise.all(
      job.outputs
        .filter((o) => o.type === "asset" && o.asset_id)
        .map((o) => fetchAssetBlob(o.asset_id!).then(URL.createObjectURL)),
    ).then(setImages);
  }, [job]);

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
        width,
        height,
        steps,
        seed,
        inputs: Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== "")),
      }),
    onSuccess: (j) => {
      setError(null);
      setImages([]);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">文生图</h1>
      <Card>
        <CardHeader>
          <CardTitle>生成</CardTitle>
          <CardDescription>
            {isComfy ? "ComfyUI 工作流驱动，参数由工作流包动态渲染。" : "在线图像 API。"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
              value={provider?.id ?? ""}
              onChange={(e) => setProviderId(Number(e.target.value))}
            >
              {imageProviders?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {isComfy && (
              <select
                className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
                value={pack?.name ?? ""}
                onChange={(e) => setWorkflow(e.target.value)}
              >
                {packs?.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex gap-2">
            <textarea
              className="min-h-24 flex-1 rounded-md border border-border bg-transparent p-3 text-sm placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
              placeholder="提示词…"
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
          <Input
            placeholder="负面提示词（可选）"
            value={negative}
            onChange={(e) => setNegative(e.target.value)}
          />
          <div className="grid gap-3 sm:grid-cols-4">
            <Input type="number" value={width} onChange={(e) => setWidth(Number(e.target.value))} placeholder="宽" />
            <Input type="number" value={height} onChange={(e) => setHeight(Number(e.target.value))} placeholder="高" />
            <Input type="number" value={steps} onChange={(e) => setSteps(Number(e.target.value))} placeholder="步数" />
            <Input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} placeholder="种子 -1 随机" />
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
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>
        </CardContent>
      </Card>

      {images.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {images.map((url) => (
            <img key={url} src={url} alt="生成结果" className="w-full rounded-lg border border-border" />
          ))}
        </div>
      )}
    </div>
  );
}

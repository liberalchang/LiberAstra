import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useJob } from "@/hooks/useJob";

interface Props {
  /** i2i = 图生图与编辑；upscale = 修复与放大 */
  capability: "i2i" | "upscale";
  title: string;
  description: string;
}

export function ImageEditPage({ capability, title, description }: Props) {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const imageProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("image"));

  const [providerId, setProviderId] = useState<number | "">("");
  const provider = imageProviders?.find((p) => p.id === providerId) ?? imageProviders?.[0];
  const isComfy = provider?.type === "comfyui";

  const { data: packs } = useQuery({
    queryKey: ["workflows", capability],
    queryFn: () => api.listWorkflows(capability),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = useState("");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
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

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files ?? []) form.append("images", f);
      form.set("prompt", prompt);
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
      setImages([]);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const noPacks = isComfy && packs && packs.length === 0;

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
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
          {noPacks && (
            <p className="text-sm text-muted-foreground">
              没有 {capability} 能力的工作流包，请到「设置 → 工作流包」导入。
            </p>
          )}
          <Input type="file" accept="image/*" multiple onChange={(e) => setFiles(e.target.files)} />
          <Input
            placeholder={capability === "i2i" ? "编辑提示词（如：把背景换成海滩）" : "提示词（可选）"}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={["prompt"]}
            />
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={!files?.length || (isComfy && !pack) || submit.isPending || !!running}
            >
              {running ? `处理中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始"}
            </Button>
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>
        </CardContent>
      </Card>

      {images.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {images.map((url) => (
            <img key={url} src={url} alt="处理结果" className="w-full rounded-lg border border-border" />
          ))}
        </div>
      )}
    </div>
  );
}

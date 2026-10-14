import { useMutation, useQuery } from "@tanstack/react-query";
import { ImageUp, WandSparkles } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
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

  const [prompt, setPrompt] = usePersistentState(`image-${capability}:prompt`, "");
  const [files, setFiles] = useState<FileList | null>(null);
  const [extra, setExtra] = usePersistentState<Record<string, string>>(`image-${capability}:extra`, {});
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob(`image-${capability}`);

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
          <Field label="原图" hint="可多选，也可以直接拖拽进来。图生图和放大都从这些图片开始。">
            <FileDrop
              accept="image/*"
              multiple
              title="点击或拖拽上传图片"
              subtitle="支持多选"
              names={files ? Array.from(files).map((f) => f.name) : []}
              onSelect={(fs) => setFiles(fs)}
            />
          </Field>
          <Field
            label="提示词"
            hint={capability === "i2i" ? "说明要怎么改，例如把背景换成海滩。" : "放大或修复时可选，用来约束画面。"}
          >
            <Input
              placeholder={capability === "i2i" ? "例如：把背景换成海滩" : "可选"}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </Field>
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
              { label: "提示词", value: prompt },
            ]}
          />
        }
      />
    </div>
  );
}

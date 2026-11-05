import { Loader2, Video } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import { AssetPickButton } from "@/components/AssetPickButton";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileDrop } from "@/components/ui/file-drop";
import { Field } from "@/components/ui/field";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";
import { assetAsFile } from "@/lib/assets";

export function VideoEnhancePage() {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const videoProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("video"));
  const [providerId, setProviderId] = usePersistentState<number | "">("tool-video-enhance:provider", "");
  const provider = videoProviders?.find((p) => p.id === providerId) ?? videoProviders?.[0];
  const isComfy = provider?.type === "comfyui";

  const { data: packs } = useQuery({
    queryKey: ["workflows", "v2v"],
    queryFn: () => api.listWorkflows("v2v"),
    enabled: isComfy,
  });
  const [workflow, setWorkflow] = usePersistentState("tool-video-enhance:workflow", "");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];
  const [extra, setExtra] = usePersistentState<Record<string, string>>(
    `tool-video-enhance:extra:${pack?.name ?? "none"}`,
    {},
  );
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("tool-video-enhance");

  const submit = useMutation({
    mutationFn: async () => {
      if (!file || !pack) throw new Error(tx("请选择视频和工作流"));
      const form = new FormData();
      form.set("video", file);
      form.set("workflow", pack.name);
      if (provider) form.set("provider_id", String(provider.id));
      form.set("inputs", JSON.stringify(extra));
      return api.submitVideoEdit(form);
    },
    onSuccess: (created) => {
      setJobId(created.id);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const busy = submit.isPending || (job != null && !["succeeded", "failed", "canceled"].includes(job.status));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="clips"
        icon={Video}
        title={tx("视频增强")}
        description={tx("用 SeedVR2 对视频做修复和放大，保留原 fps 和音频。")}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{tx("输入")}</CardTitle>
            <CardDescription>{tx("建议先用很短的片段测试；长片耗时较长。")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Field label={tx("视频")} hint={tx("可以上传新视频，也可以直接选资源库里的视频。")}>
              <FileDrop accept="video/*" title={file ? file.name : tx("点击或拖拽上传视频")} onSelect={(files) => setFile(files?.[0] ?? null)} />
              <AssetPickButton
                kind="video"
                onPick={async (assets) => {
                  if (assets[0]) setFile(await assetAsFile(assets[0]));
                }}
              />
            </Field>
            {videoProviders && videoProviders.length > 1 && (
              <Field label={tx("视频服务")}>
                <select
                  className="h-11 w-full rounded-[10px] border border-border bg-field px-3 text-sm"
                  value={provider?.id ?? ""}
                  onChange={(event) => setProviderId(event.target.value ? Number(event.target.value) : "")}
                >
                  {videoProviders.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </Field>
            )}
            {isComfy && (
              <Field label={tx("工作流包")}>
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
            {!isComfy && <p className="text-sm text-warning">{tx("视频增强需要启用的 ComfyUI Provider。")}</p>}
            {isComfy && pack && (
              <AdvancedPanel summary={tx("模型与采样")}>
                <WorkflowInputs
                  inputs={pack.inputs}
                  values={extra}
                  onChange={(key, value) => setExtra((prev) => ({ ...prev, [key]: value }))}
                  exclude={["video"]}
                  providerId={provider?.id}
                />
              </AdvancedPanel>
            )}
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className={submitButtonClass} disabled={!file || !pack || busy} onClick={() => submit.mutate()}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {tx("开始增强")}
            </Button>
          </CardContent>
        </Card>
        <ResultPanel job={job ?? null} mediaKind="video" historyKind="video" jobFunction="video.v2v" emptyHint={tx("增强后的视频会出现在这里")} />
      </div>
    </div>
  );
}

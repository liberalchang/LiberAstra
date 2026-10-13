import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Mic } from "lucide-react";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { useJob } from "@/hooks/useJob";

export function AsrPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const asrProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("asr"));

  const [providerId, setProviderId] = useState<number | "">("");
  const [language, setLanguage] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId).data;

  useEffect(() => {
    if (job?.status === "failed") setError(job.error ?? "任务失败");
  }, [job]);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("file", file!);
      if (providerId !== "") form.set("provider_id", String(providerId));
      if (language) form.set("language", language);
      return api.submitAsr(form);
    },
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const download = async (assetId: number, filename: string) => {
    const blob = await fetchAssetBlob(assetId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const running = job && (job.status === "pending" || job.status === "running");
  const textOutput = job?.outputs.find((o) => o.type === "text");
  const fileOutputs = job?.outputs.filter((o) => o.type === "asset" && o.asset_id) ?? [];

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader kind="asr" icon={Mic} title="语音转文字" description="上传音频，导出文本和字幕。" />
      <Card>
        <CardHeader>
          <CardTitle>转写</CardTitle>
          <CardDescription>上传音频，输出文本与 srt / vtt / json 字幕。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="识别服务" hint="留空则使用第一个已启用的 ASR Provider。本机不内置识别模型。">
              <select
                className={selectClass}
                value={providerId}
                onChange={(e) => setProviderId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">默认 Provider</option>
                {asrProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="语言" hint="可选。例如 zh、en。留空时由识别服务自行判断。">
              <Input
                placeholder="如 zh、en"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              />
            </Field>
          </div>
          <Field label="音频文件" hint="支持音频或视频，可直接拖拽。完成后给出文本，以及 srt / vtt / json 字幕。">
            <FileDrop
              accept="audio/*,video/*"
              title="点击或拖拽上传音频"
              subtitle="支持音频和视频文件"
              names={file ? [file.name] : []}
              onSelect={(fs) => setFile(fs?.[0] ?? null)}
            />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!file || submit.isPending || !!running}>
              {running ? `转写中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始转写"}
            </Button>
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>

          {textOutput?.content && (
            <div className="rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">
              {textOutput.content}
            </div>
          )}
          {fileOutputs.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {fileOutputs.map((o) => (
                <Button
                  key={o.asset_id}
                  variant="outline"
                  size="sm"
                  onClick={() => download(o.asset_id!, o.filename ?? `transcript.${o.format}`)}
                >
                  <Download /> {o.format}
                </Button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

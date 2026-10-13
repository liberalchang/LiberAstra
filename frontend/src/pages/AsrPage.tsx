import { useMutation, useQuery } from "@tanstack/react-query";
import { Mic } from "lucide-react";
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
import { useTrackedJob } from "@/hooks/useJob";

export function AsrPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const asrProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("asr"));

  const [providerId, setProviderId] = useState<number | "">("");
  const [language, setLanguage] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("asr");

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

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="asr" icon={Mic} title="语音转文字" description="上传音频，导出文本和字幕。" />
      <SplitPane
        storageKey="asr"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
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
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind={null}
            historyKind="subtitle"
            emptyHint="上传音频，转写出文本和字幕"
            meta={[
              { label: "服务", value: asrProviders?.find((p) => p.id === providerId)?.name ?? "" },
              { label: "语言", value: language },
              { label: "文件", value: file?.name ?? "" },
            ]}
          />
        }
      />
    </div>
  );
}

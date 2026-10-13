import { useMutation, useQuery } from "@tanstack/react-query";
import { AudioLines } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { useTrackedJob } from "@/hooks/useJob";

export function TtsPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const ttsProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("tts"));

  const [providerId, setProviderId] = useState<number | "">("");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [format, setFormat] = useState("mp3");
  const location = useLocation();
  const [text, setText] = useState(
    () => (location.state as { prompt?: string } | null)?.prompt ?? "",
  );
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("tts");

  const submit = useMutation({
    mutationFn: () =>
      api.submitTts({
        provider_id: providerId === "" ? undefined : providerId,
        voice_record_id: voiceRecordId === "" ? undefined : voiceRecordId,
        voice: voiceRecordId === "" ? voiceName : undefined,
        text,
        format,
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
      <PageHeader kind="tts" icon={AudioLines} title="文字转语音" description="选择音色，把文本合成为语音文件。" />
      <SplitPane
        storageKey="tts"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="语音服务" hint="留空则使用第一个已启用的 TTS Provider。">
              <select
                className={selectClass}
                value={providerId}
                onChange={(e) => setProviderId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">默认 Provider</option>
                {ttsProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="音色记录" hint="选自音色库。不选则在下面手动填写音色名。">
              <select
                className={selectClass}
                value={voiceRecordId}
                onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">手动指定音色…</option>
                {voices?.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                    {v.is_default ? "（默认）" : ""}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="输出格式" hint="Edge TTS 只支持 mp3。wav / ogg 需要兼容服务。">
              <select className={selectClass} value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="mp3">mp3</option>
                <option value="wav">wav</option>
                <option value="ogg_opus">ogg_opus</option>
              </select>
            </Field>
          </div>
          {voiceRecordId === "" && (
            <Field label="音色名" hint="需与所选服务匹配，例如 zh-CN-XiaoxiaoNeural、alloy、af_heart。">
              <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
            </Field>
          )}
          <Field label="合成文本" hint="这段文字会按所选音色朗读。">
            <textarea
              className={`${areaClass} min-h-32`}
              placeholder="输入要合成的文本…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={!text || (voiceRecordId === "" && !voiceName) || submit.isPending || !!running}
            >
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
            </Button>
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="audio"
            historyKind="audio"
            emptyHint="输入文本，合成第一段语音"
            meta={[
              { label: "服务", value: ttsProviders?.find((p) => p.id === providerId)?.name ?? "" },
              { label: "音色", value: voiceRecordId === "" ? voiceName : (voices?.find((v) => v.id === voiceRecordId)?.name ?? "") },
              { label: "格式", value: format },
            ]}
          />
        }
      />
    </div>
  );
}

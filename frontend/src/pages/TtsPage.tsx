import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useJob } from "@/hooks/useJob";

export function TtsPage() {
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const ttsProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("tts"));

  const [providerId, setProviderId] = useState<number | "">("");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [format, setFormat] = useState("mp3");
  const [text, setText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId).data;

  useEffect(() => {
    if (!job || job.status !== "succeeded") return;
    const output = job.outputs.find((o) => o.type === "asset" && o.asset_id);
    if (!output?.asset_id) return;
    let revoked = false;
    fetchAssetBlob(output.asset_id).then((blob) => {
      if (!revoked) setAudioUrl(URL.createObjectURL(blob));
    });
    return () => {
      revoked = true;
    };
  }, [job]);

  useEffect(() => {
    if (job?.status === "failed") setError(job.error ?? "任务失败");
  }, [job]);

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
      setAudioUrl(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">文字转语音</h1>
      <Card>
        <CardHeader>
          <CardTitle>合成</CardTitle>
          <CardDescription>选择 Provider 与音色，文本转为语音文件。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
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
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
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
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="mp3">mp3</option>
              <option value="wav">wav</option>
              <option value="ogg_opus">ogg_opus</option>
            </select>
          </div>
          {voiceRecordId === "" && (
            <Input
              placeholder="音色名（如 zh-CN-XiaoxiaoNeural、alloy、af_heart）"
              value={voiceName}
              onChange={(e) => setVoiceName(e.target.value)}
            />
          )}
          <textarea
            className="min-h-32 w-full rounded-md border border-border bg-transparent p-3 text-sm placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
            placeholder="输入要合成的文本…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={!text || (voiceRecordId === "" && !voiceName) || submit.isPending || !!running}
            >
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
            </Button>
            {job?.status === "succeeded" && (
              <span className="text-sm text-green-600">完成</span>
            )}
          </div>
          {audioUrl && <audio controls src={audioUrl} className="w-full" />}
        </CardContent>
      </Card>
    </div>
  );
}

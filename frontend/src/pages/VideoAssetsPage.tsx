import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useJob } from "@/hooks/useJob";

export function VideoAssetsPage() {
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [files, setFiles] = useState<FileList | null>(null);
  const [mode, setMode] = useState<"script" | "topic">("script");
  const [script, setScript] = useState("");
  const [topic, setTopic] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId).data;

  useEffect(() => {
    if (job?.status === "failed") setError(job.error ?? "任务失败");
    if (job?.status !== "succeeded") return;
    const video = job.outputs.find((o) => o.kind === "video" && o.asset_id);
    if (video?.asset_id) {
      fetchAssetBlob(video.asset_id).then((b) => setVideoUrl(URL.createObjectURL(b)));
    }
  }, [job]);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files ?? []) form.append("images", f);
      if (mode === "script") form.set("script", script);
      else form.set("topic", topic);
      form.set("aspect", aspect);
      if (voiceRecordId !== "") form.set("voice_record_id", String(voiceRecordId));
      else form.set("voice", voiceName);
      return api.submitVideoAssets(form);
    },
    onSuccess: (j) => {
      setError(null);
      setVideoUrl(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const ready =
    files?.length && (mode === "script" ? script : topic) && (voiceRecordId !== "" || voiceName);

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">自定义素材</h1>
      <Card>
        <CardHeader>
          <CardTitle>素材成片</CardTitle>
          <CardDescription>
            上传图片素材，文案逐图配音（或 LLM 按主题生成），加字幕后拼接成片。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input type="file" accept="image/*" multiple onChange={(e) => setFiles(e.target.files)} />
          <div className="flex gap-2">
            <Button variant={mode === "script" ? "default" : "outline"} size="sm" onClick={() => setMode("script")}>
              自备文案（按行对应图片）
            </Button>
            <Button variant={mode === "topic" ? "default" : "outline"} size="sm" onClick={() => setMode("topic")}>
              主题生成文案
            </Button>
          </div>
          {mode === "script" ? (
            <textarea
              className="min-h-24 w-full rounded-md border border-border bg-transparent p-3 text-sm"
              placeholder="每行一句口播，与图片一一对应…"
              value={script}
              onChange={(e) => setScript(e.target.value)}
            />
          ) : (
            <Input placeholder="主题" value={topic} onChange={(e) => setTopic(e.target.value)} />
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <select className="h-9 rounded-md border border-border bg-transparent px-3 text-sm" value={aspect} onChange={(e) => setAspect(e.target.value)}>
              <option value="9:16">9:16</option>
              <option value="1:1">1:1</option>
              <option value="16:9">16:9</option>
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
                </option>
              ))}
            </select>
            {voiceRecordId === "" && (
              <Input placeholder="音色名" value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
            )}
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
            </Button>
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>
        </CardContent>
      </Card>

      {videoUrl && <video controls src={videoUrl} className="w-full rounded-lg border border-border" />}
    </div>
  );
}

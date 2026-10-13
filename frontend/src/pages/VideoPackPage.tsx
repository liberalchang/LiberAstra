import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob, type JobOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useJob } from "@/hooks/useJob";

export type PackVideoKind = "i2v" | "avatar" | "motion";

const CONFIG: Record<
  PackVideoKind,
  { title: string; description: string; packCaps: string[]; submit: (f: FormData) => Promise<JobOut> }
> = {
  i2v: {
    title: "图生视频",
    description: "上传首帧图片 + 提示词，交给 first_frame_i2v 工作流。",
    packCaps: ["i2v", "first_frame_i2v"],
    submit: api.submitVideoI2v,
  },
  avatar: {
    title: "数字人口播",
    description: "人物图 + 口播文案 → TTS → digital_human 工作流。",
    packCaps: ["digital", "digital_human"],
    submit: api.submitVideoAvatar,
  },
  motion: {
    title: "动作迁移",
    description: "参考视频（≤30s）+ 目标图片 + 提示词 → action_transfer 工作流。",
    packCaps: ["action", "action_transfer"],
    submit: api.submitVideoMotion,
  },
};

export function VideoPackPage({ kind }: { kind: PackVideoKind }) {
  const cfg = CONFIG[kind];
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const videoProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("video"));
  const [providerId, setProviderId] = useState<number | "">("");
  const provider = videoProviders?.find((p) => p.id === providerId) ?? videoProviders?.[0];

  const { data: allPacks } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });
  const packs = allPacks?.filter((p) => cfg.packCaps.includes(p.capability));
  const [workflow, setWorkflow] = useState("");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [text, setText] = useState("");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [extra, setExtra] = useState<Record<string, string>>({});
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
      if (kind === "motion" && videoFile) form.set("video", videoFile);
      if (imageFile) form.set("image", imageFile);
      form.set("workflow", pack?.name ?? "");
      form.set("prompt", prompt);
      if (kind === "avatar") {
        form.set("text", text);
        if (voiceRecordId !== "") form.set("voice_record_id", String(voiceRecordId));
        else form.set("voice", voiceName);
      }
      if (provider) form.set("provider_id", String(provider.id));
      form.set(
        "inputs",
        JSON.stringify(Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== ""))),
      );
      return cfg.submit(form);
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
    pack &&
    imageFile &&
    (kind !== "motion" || videoFile) &&
    (kind !== "avatar" || (text && (voiceRecordId !== "" || voiceName)));

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">{cfg.title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>{cfg.title}</CardTitle>
          <CardDescription>{cfg.description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
              value={provider?.id ?? ""}
              onChange={(e) => setProviderId(Number(e.target.value))}
            >
              {videoProviders?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
              value={pack?.name ?? ""}
              onChange={(e) => setWorkflow(e.target.value)}
            >
              {packs?.length ? (
                packs.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))
              ) : (
                <option value="">无 {cfg.packCaps.join("/")} 工作流包</option>
              )}
            </select>
          </div>

          {kind === "motion" && (
            <Input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)} />
          )}
          <Input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] ?? null)} />

          {kind === "avatar" ? (
            <>
              <textarea
                className="min-h-24 w-full rounded-md border border-border bg-transparent p-3 text-sm"
                placeholder="口播文案…"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <div className="grid gap-3 sm:grid-cols-2">
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
            </>
          ) : (
            <Input placeholder="提示词" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          )}

          {pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={["prompt", "image", "video", "audio"]}
            />
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? `生成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始生成"}
            </Button>
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>
        </CardContent>
      </Card>

      {videoUrl && <video controls src={videoUrl} className="w-full rounded-lg border border-border" />}
    </div>
  );
}

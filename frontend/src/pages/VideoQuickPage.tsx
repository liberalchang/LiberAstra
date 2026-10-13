import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useJob } from "@/hooks/useJob";

export function VideoQuickPage() {
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [mode, setMode] = useState<"topic" | "script">("topic");
  const [topic, setTopic] = useState("");
  const [script, setScript] = useState("");
  const [splitMode, setSplitMode] = useState("paragraph");
  const [count, setCount] = useState(4);
  const [aspect, setAspect] = useState("9:16");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [stylePrefix, setStylePrefix] = useState("");
  const [storyboardOnly, setStoryboardOnly] = useState(false);
  const [bgmFile, setBgmFile] = useState<File | null>(null);

  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [storyboardText, setStoryboardText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId).data;

  useEffect(() => {
    if (job?.status === "failed") setError(job.error ?? "任务失败");
    if (job?.status !== "succeeded") return;
    const video = job.outputs.find((o) => o.kind === "video" && o.asset_id);
    if (video?.asset_id) {
      fetchAssetBlob(video.asset_id).then((b) => setVideoUrl(URL.createObjectURL(b)));
    }
    const sb = job.outputs.find((o) => o.kind === "storyboard" && o.asset_id);
    if (sb?.asset_id) {
      fetchAssetBlob(sb.asset_id).then(async (b) => {
        setStoryboardText(JSON.stringify(JSON.parse(await b.text()), null, 2));
      });
    }
  }, [job]);

  const buildBody = async (storyboard?: unknown) => {
    let bgm_path: string | undefined;
    if (bgmFile) bgm_path = (await api.uploadFile(bgmFile)).path;
    return {
      topic: mode === "topic" ? topic : undefined,
      script: mode === "script" ? script : undefined,
      split_mode: splitMode,
      storyboard_count: count,
      aspect,
      voice_record_id: voiceRecordId === "" ? undefined : voiceRecordId,
      voice: voiceRecordId === "" ? voiceName : undefined,
      style_prefix: stylePrefix,
      storyboard,
      storyboard_only: storyboardOnly,
      bgm_path,
    };
  };

  const submit = useMutation({
    mutationFn: async () => api.submitQuickVideo(await buildBody()),
    onSuccess: (j) => {
      setError(null);
      setVideoUrl(null);
      setStoryboardText(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const resubmit = useMutation({
    mutationFn: async () => {
      let storyboard: unknown;
      try {
        storyboard = JSON.parse(storyboardText ?? "");
      } catch (e) {
        throw new Error(`分镜 JSON 解析失败: ${(e as Error).message}`);
      }
      return api.submitQuickVideo(await buildBody(storyboard));
    },
    onSuccess: (j) => {
      setError(null);
      setVideoUrl(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">快速创作</h1>
      <Card>
        <CardHeader>
          <CardTitle>一句话出短视频</CardTitle>
          <CardDescription>LLM 写文案与分镜 → 逐帧 TTS + 图像 → 字幕分段 → 拼接加 BGM。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button variant={mode === "topic" ? "default" : "outline"} size="sm" onClick={() => setMode("topic")}>
              输入主题
            </Button>
            <Button variant={mode === "script" ? "default" : "outline"} size="sm" onClick={() => setMode("script")}>
              固定文案
            </Button>
          </div>
          {mode === "topic" ? (
            <Input placeholder="主题（如：三个提高效率的小技巧）" value={topic} onChange={(e) => setTopic(e.target.value)} />
          ) : (
            <textarea
              className="min-h-28 w-full rounded-md border border-border bg-transparent p-3 text-sm"
              placeholder="口播文案，按下方方式切分…"
              value={script}
              onChange={(e) => setScript(e.target.value)}
            />
          )}
          <div className="grid gap-3 sm:grid-cols-4">
            {mode === "script" && (
              <select className="h-9 rounded-md border border-border bg-transparent px-3 text-sm" value={splitMode} onChange={(e) => setSplitMode(e.target.value)}>
                <option value="paragraph">按段切分</option>
                <option value="line">按行切分</option>
                <option value="sentence">按句切分</option>
              </select>
            )}
            {mode === "topic" && (
              <Input type="number" min={1} max={12} value={count} onChange={(e) => setCount(Number(e.target.value))} placeholder="分镜数" />
            )}
            <select className="h-9 rounded-md border border-border bg-transparent px-3 text-sm" value={aspect} onChange={(e) => setAspect(e.target.value)}>
              <option value="9:16">9:16 竖屏</option>
              <option value="1:1">1:1 方形</option>
              <option value="16:9">16:9 横屏</option>
            </select>
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm sm:col-span-2"
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
          </div>
          {voiceRecordId === "" && (
            <Input placeholder="音色名（如 zh-CN-XiaoxiaoNeural、alloy）" value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Input placeholder="风格前缀（可选，如：电影感，浅景深，）" value={stylePrefix} onChange={(e) => setStylePrefix(e.target.value)} />
            <Input type="file" accept="audio/*" onChange={(e) => setBgmFile(e.target.files?.[0] ?? null)} placeholder="BGM（可选）" />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={storyboardOnly} onChange={(e) => setStoryboardOnly(e.target.checked)} />
            仅生成分镜（供人工修改后再合成）
          </label>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={(mode === "topic" ? !topic : !script) || (voiceRecordId === "" && !voiceName) || submit.isPending || !!running}
            >
              {running ? `进行中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始创作"}
            </Button>
            {running && job?.steps?.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {String(job.steps[job.steps.length - 1]?.name ?? "")}
              </span>
            )}
            {job?.status === "succeeded" && <span className="text-sm text-green-600">完成</span>}
          </div>
        </CardContent>
      </Card>

      {videoUrl && <video controls src={videoUrl} className="w-full rounded-lg border border-border" />}

      {storyboardText && (
        <Card>
          <CardHeader>
            <CardTitle>分镜编辑</CardTitle>
            <CardDescription>修改 frames 后重新合成（跳过 LLM）。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <textarea
              className="min-h-48 w-full rounded-md border border-border bg-transparent p-3 font-mono text-xs"
              value={storyboardText}
              onChange={(e) => setStoryboardText(e.target.value)}
            />
            <Button className="w-fit" variant="outline" onClick={() => resubmit.mutate()} disabled={resubmit.isPending || !!running}>
              按修改后的分镜重新合成
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

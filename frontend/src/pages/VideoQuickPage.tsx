import { Clapperboard } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api, fetchAssetBlob } from "@/api/client";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";

export function VideoQuickPage() {
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [mode, setMode] = usePersistentState<"topic" | "script">("video-quick:mode", "topic");
  const location = useLocation();
  const incomingTopic = (location.state as { prompt?: string } | null)?.prompt;
  const [topic, setTopic] = usePersistentState("video-quick:topic", "");
  // 从其他页面带过来的主题优先于本地记忆
  useEffect(() => {
    if (incomingTopic) setTopic(incomingTopic);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [script, setScript] = usePersistentState("video-quick:script", "");
  const [splitMode, setSplitMode] = usePersistentState("video-quick:split-mode", "paragraph");
  const [count, setCount] = usePersistentState("video-quick:count", 4);
  const [aspect, setAspect] = usePersistentState("video-quick:aspect", "9:16");
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("video-quick:voice-record", "");
  const [voiceName, setVoiceName] = usePersistentState("video-quick:voice-name", "");
  const [stylePrefix, setStylePrefix] = usePersistentState("video-quick:style-prefix", "");
  const [storyboardOnly, setStoryboardOnly] = usePersistentState("video-quick:storyboard-only", false);
  const [bgmFile, setBgmFile] = useState<File | null>(null);

  const [storyboardText, setStoryboardText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { job, setJobId } = useTrackedJob("video-quick");

  useEffect(() => {
    if (job?.status !== "succeeded") return;
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
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="video" icon={Clapperboard} title="快速创作" description="一句话出短视频：文案、分镜、配音、字幕和拼接。" />
      <SplitPane
        storageKey="video-quick"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <Segmented
            ariaLabel="文案来源"
            options={[
              { value: "topic", label: "输入主题" },
              { value: "script", label: "固定文案" },
            ]}
            value={mode}
            onChange={setMode}
          />
          {mode === "topic" ? (
            <Field label="主题" hint="用一句话说明短视频讲什么，例如三个提高效率的小技巧。">
              <Input value={topic} onChange={(e) => setTopic(e.target.value)} />
            </Field>
          ) : (
            <Field label="口播文案" hint="按下方切分方式拆成多个分镜。">
              <textarea
                className={`${areaClass} min-h-28`}
                value={script}
                onChange={(e) => setScript(e.target.value)}
              />
            </Field>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {mode === "script" && (
              <Field label="切分方式" hint="决定文案如何拆成一条条分镜。">
                <select className={selectClass} value={splitMode} onChange={(e) => setSplitMode(e.target.value)}>
                  <option value="paragraph">按段切分</option>
                  <option value="line">按行切分</option>
                  <option value="sentence">按句切分</option>
                </select>
              </Field>
            )}
            {mode === "topic" && (
              <Field label="分镜数" hint="范围 1 到 12。主题模式下由模型拆成这么多镜。">
                <Input type="number" min={1} max={12} value={count} onChange={(e) => setCount(Number(e.target.value))} />
              </Field>
            )}
            <Field label="画幅" hint="竖屏适合短视频，横屏适合宽画面。">
              <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
                <option value="9:16">9:16 竖屏</option>
                <option value="1:1">1:1 方形</option>
                <option value="16:9">16:9 横屏</option>
              </select>
            </Field>
            <Field label="音色" hint="选自音色库。不选则在下方填写音色名。">
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
          </div>
          {voiceRecordId === "" && (
            <Field label="音色名" hint="需与当前 TTS 服务匹配，例如 zh-CN-XiaoxiaoNeural、alloy。">
              <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
            </Field>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="风格前缀" hint="会加在每个分镜提示词前面，可以留空。">
              <Input value={stylePrefix} onChange={(e) => setStylePrefix(e.target.value)} placeholder="例如：电影感，浅景深，" />
            </Field>
            <Field label="背景音乐" hint="可选。上传后会混进成片。">
              <FileDrop
                accept="audio/*"
                title="点击或拖拽上传 BGM"
                subtitle="可选"
                names={bgmFile ? [bgmFile.name] : []}
                onSelect={(fs) => setBgmFile(fs?.[0] ?? null)}
              />
            </Field>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">分镜确认</span>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={storyboardOnly} onChange={(e) => setStoryboardOnly(e.target.checked)} />
              仅生成分镜（供人工修改后再合成）
            </label>
            <span className="text-xs leading-relaxed text-muted-foreground">勾选后只出分镜 JSON，确认后再合成视频。</span>
          </div>
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
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            emptyHint="一句话或一段文案，生成一条短视频"
            meta={[
              { label: "画幅", value: aspect },
              { label: "音色", value: voiceRecordId === "" ? voiceName : (voices?.find((v) => v.id === voiceRecordId)?.name ?? "") },
              { label: "内容", value: mode === "topic" ? topic : script },
            ]}
          />
        }
      />

      {storyboardText && (
        <Card>
          <CardHeader>
            <CardTitle>分镜编辑</CardTitle>
            <CardDescription>修改 frames 后重新合成（跳过 LLM）。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Field label="分镜 JSON" hint="修改 frames 后重新合成。这一步会跳过 LLM。">
              <textarea
                className={`${areaClass} min-h-48 font-mono text-xs`}
                value={storyboardText}
                onChange={(e) => setStoryboardText(e.target.value)}
              />
            </Field>
            <Button className="w-fit" variant="outline" onClick={() => resubmit.mutate()} disabled={resubmit.isPending || !!running}>
              按修改后的分镜重新合成
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

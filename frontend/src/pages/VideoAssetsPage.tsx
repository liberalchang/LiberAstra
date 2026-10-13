import { Images } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { useTrackedJob } from "@/hooks/useJob";

export function VideoAssetsPage() {
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [files, setFiles] = useState<FileList | null>(null);
  const [mode, setMode] = useState<"script" | "topic">("script");
  const [script, setScript] = useState("");
  const [topic, setTopic] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [voiceRecordId, setVoiceRecordId] = useState<number | "">("");
  const [voiceName, setVoiceName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { job, setJobId } = useTrackedJob("video-assets");

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
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const ready =
    files?.length && (mode === "script" ? script : topic) && (voiceRecordId !== "" || voiceName);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="clips" icon={Images} title="自定义素材" description="上传图片素材，配旁白和字幕后拼成短片。" />
      <SplitPane
        storageKey="video-assets"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <Field label="图片素材" hint="可多选或直接拖拽。顺序与口播文案的行一一对应。">
            <FileDrop
              accept="image/*"
              multiple
              title="点击或拖拽上传素材图片"
              subtitle="支持多选，按文件名顺序排列"
              names={files ? Array.from(files).map((f) => f.name) : []}
              onSelect={(fs) => setFiles(fs)}
            />
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">文案来源</span>
            <Segmented
              ariaLabel="文案来源"
              options={[
                { value: "script", label: "自备文案（按行对应图片）" },
                { value: "topic", label: "主题生成文案" },
              ]}
              value={mode}
              onChange={setMode}
            />
            <span className="text-xs leading-relaxed text-muted-foreground">自备文案时，每一行对应一张图片。</span>
          </div>
          {mode === "script" ? (
            <Field label="口播文案" hint="每行一句，行数建议与图片数量一致。">
              <textarea
                className={`${areaClass} min-h-24`}
                value={script}
                onChange={(e) => setScript(e.target.value)}
              />
            </Field>
          ) : (
            <Field label="主题" hint="由 LLM 按图片数量生成口播。">
              <Input value={topic} onChange={(e) => setTopic(e.target.value)} />
            </Field>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="画幅" hint="成片宽高比。">
              <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
                <option value="9:16">9:16 竖屏</option>
                <option value="1:1">1:1 方形</option>
                <option value="16:9">16:9 横屏</option>
              </select>
            </Field>
            <Field label="音色" hint="选自音色库。不选则填写音色名。">
              <select
                className={selectClass}
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
            </Field>
            {voiceRecordId === "" && (
              <Field label="音色名" hint="例如 zh-CN-XiaoxiaoNeural、alloy。">
                <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
              </Field>
            )}
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
            </Button>
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            emptyHint="上传素材图片，拼成一条短片"
            meta={[
              { label: "画幅", value: aspect },
              { label: "音色", value: voiceRecordId === "" ? voiceName : (voices?.find((v) => v.id === voiceRecordId)?.name ?? "") },
              { label: "内容", value: mode === "script" ? script : topic },
            ]}
          />
        }
      />
    </div>
  );
}

import { Film, PersonStanding, UserRound } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, type JobOut } from "@/api/client";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";

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
  const [providerId, setProviderId] = usePersistentState<number | "">(`video-${kind}:provider`, "");
  const provider = videoProviders?.find((p) => p.id === providerId) ?? videoProviders?.[0];

  const { data: allPacks } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });
  const packs = allPacks?.filter((p) => cfg.packCaps.includes(p.capability));
  const [workflow, setWorkflow] = usePersistentState(`video-${kind}:workflow`, "");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [prompt, setPrompt] = usePersistentState(`video-${kind}:prompt`, "");
  const [text, setText] = usePersistentState(`video-${kind}:text`, "");
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">(`video-${kind}:voice-record`, "");
  const [voiceName, setVoiceName] = usePersistentState(`video-${kind}:voice-name`, "");
  const [extra, setExtra] = usePersistentState<Record<string, string>>(`video-${kind}:extra`, {});
  const [error, setError] = useState<string | null>(null);

  const { job, setJobId } = useTrackedJob(`video-${kind}`);

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
    <div className="flex flex-col gap-6">
      <PageHeader kind={kind === "avatar" ? "avatar" : kind === "motion" ? "motion" : "i2v"} icon={kind === "avatar" ? UserRound : kind === "motion" ? PersonStanding : Film} title={cfg.title} description={cfg.description} />
      <SplitPane
        storageKey={`video-${kind}`}
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="视频服务" hint="只列出已启用、且具备 video 能力的 Provider。">
              <select
                className={selectClass}
                value={provider?.id ?? ""}
                onChange={(e) => setProviderId(Number(e.target.value))}
              >
                {videoProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="工作流包" hint="必须与当前功能匹配，例如图生视频、数字人或动作迁移。">
              <select
                className={selectClass}
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
            </Field>
          </div>

          {kind === "motion" && (
            <Field label="参考视频" hint="动作来源，建议不超过 30 秒。">
              <FileDrop
                accept="video/*"
                title="点击或拖拽上传参考视频"
                subtitle="建议不超过 30 秒"
                names={videoFile ? [videoFile.name] : []}
                onSelect={(fs) => setVideoFile(fs?.[0] ?? null)}
              />
            </Field>
          )}
          <Field label={kind === "avatar" ? "人物图片" : "图片"} hint={kind === "i2v" ? "作为视频首帧。" : "目标人物或画面。"}>
            <FileDrop
              accept="image/*"
              title="点击或拖拽上传图片"
              names={imageFile ? [imageFile.name] : []}
              onSelect={(fs) => setImageFile(fs?.[0] ?? null)}
            />
          </Field>

          {kind === "avatar" ? (
            <>
              <Field label="口播文案" hint="先合成语音，再交给数字人工作流。">
                <textarea
                  className={`${areaClass} min-h-24`}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
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
                  <Field label="音色名" hint="需与当前 TTS 服务匹配。">
                    <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
                  </Field>
                )}
              </div>
            </>
          ) : (
            <Field label="提示词" hint="描述希望画面如何运动或变化。">
              <Input value={prompt} onChange={(e) => setPrompt(e.target.value)} />
            </Field>
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
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            emptyHint="上传素材，生成第一段视频"
            meta={[
              { label: "服务", value: provider?.name ?? "" },
              { label: "工作流", value: pack?.name ?? "" },
              { label: kind === "avatar" ? "文案" : "提示词", value: kind === "avatar" ? text : prompt },
            ]}
          />
        }
      />
    </div>
  );
}

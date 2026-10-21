import { Film, PersonStanding, UserRound } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, type JobOut } from "@/api/client";
import {
  AccelControl,
  buildInputsWithAccel,
  defaultAccelState,
  hasAccel,
  type AccelState,
} from "@/components/AccelControl";
import {
  PromptField,
  resolveEffectivePrompt,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { useTx } from "@/i18n/tx";

export type PackVideoKind = "i2v" | "avatar" | "motion";

const CONFIG: Record<
  PackVideoKind,
  { title: string; description: string; packCaps: string[]; submit: (f: FormData) => Promise<JobOut> }
> = {
  i2v: {
    title: "图生视频",
    description: "上传首帧图片 + 提示词，交给 i2v 工作流。",
    packCaps: ["i2v", "first_frame_i2v"],
    submit: api.submitVideoI2v,
  },
  avatar: {
    title: "数字人口播",
    description: "人物图 + 口播文案 → TTS → avatar 工作流。",
    packCaps: ["avatar", "digital", "digital_human"],
    submit: api.submitVideoAvatar,
  },
  motion: {
    title: "动作迁移",
    description: "参考视频（≤30s）+ 目标图片 + 提示词 → motion 工作流。",
    packCaps: ["motion", "action", "action_transfer"],
    submit: api.submitVideoMotion,
  },
};

export function VideoPackPage({ kind }: { kind: PackVideoKind }) {
  const tx = useTx();
  const cfg = CONFIG[kind];
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const videoProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("video"));
  const [providerId, setProviderId] = usePersistentState<number | "">(`video-${kind}:provider`, "");
  const provider = videoProviders?.find((p) => p.id === providerId) ?? videoProviders?.[0];

  const { data: allPacks } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });
  const packs = allPacks?.filter((p) => cfg.packCaps.includes(p.capability));
  const [workflow, setWorkflow] = usePersistentState(`video-${kind}:workflow`, "");
  const pack = packs?.find((p) => p.name === workflow) ?? packs?.[0];

  // 依赖预检：包声明了但服务上没有的模型文件，提前警告（不拦截）
  const missingModels = (() => {
    const declared = pack?.requirements?.models;
    const available = provider?.models ?? [];
    if (!Array.isArray(declared) || declared.length === 0 || available.length === 0) return [];
    return (declared as unknown[])
      .filter((m): m is string => typeof m === "string")
      .filter((m) => !available.some((a) => a === m || a.endsWith(m.split("/").pop() ?? m)));
  })();

  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [characterId, setCharacterId] = usePersistentState<number | "">(`video-${kind}:character`, "");
  const [characterView, setCharacterView] = usePersistentState(`video-${kind}:character-view`, "front");
  const { data: characters } = useQuery({ queryKey: ["characters"], queryFn: api.listCharacters });
  const character = characters?.find((item) => item.id === characterId);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [promptValue, setPromptValue] = usePersistentPromptValue(`video-${kind}:prompt`);
  const effectivePrompt = resolveEffectivePrompt(promptValue);
  const [text, setText] = usePersistentState(`video-${kind}:text`, "");
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">(`video-${kind}:voice-record`, "");
  const [voiceName, setVoiceName] = usePersistentState(`video-${kind}:voice-name`, "");
  const [extra, setExtra] = usePersistentState<Record<string, string>>(
    `video-${kind}:extra:${pack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(pack?.inputs, ["prompt", "image", "video", "audio", "mask"]),
  );
  const [accel, setAccel] = usePersistentState<AccelState>(
    `video-${kind}:accel:${pack?.name ?? "none"}`,
    () => defaultAccelState(pack?.accel),
  );
  // 数字人口播的配音服务：comfy 出语音工作流包，Liber Speech 出音色库，其余出服务音色列表
  const { data: ttsPacks } = useQuery({
    queryKey: ["workflows", "tts"],
    queryFn: () => api.listWorkflows("tts"),
    enabled: kind === "avatar",
  });
  const ttsProviders = providers?.filter((p) => {
    if (!p.enabled || !p.capabilities.includes("tts")) return false;
    if (p.type === "comfyui") return (ttsPacks?.length ?? 0) > 0;
    return true;
  });
  const [ttsProviderId, setTtsProviderId] = usePersistentState<number | "">(`video-${kind}:tts-provider`, "");
  const ttsProvider = ttsProviders?.find((p) => p.id === ttsProviderId) ?? ttsProviders?.[0];
  const ttsIsComfy = ttsProvider?.type === "comfyui";
  const isLibraryVoice = ttsProvider?.type === "liber_speech" || ttsProvider == null;
  const serviceVoices = isLibraryVoice || ttsIsComfy ? [] : (ttsProvider?.models ?? []);
  const [ttsWorkflow, setTtsWorkflow] = usePersistentState(`video-${kind}:tts-workflow`, "");
  const ttsPack = ttsPacks?.find((p) => p.name === ttsWorkflow) ?? ttsPacks?.[0];
  const [ttsExtra, setTtsExtra] = usePersistentState<Record<string, string>>(`video-${kind}:tts-extra`, {});
  const [error, setError] = useState<string | null>(null);

  const { job, setJobId } = useTrackedJob(`video-${kind}`);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (kind === "motion" && videoFile) form.set("video", videoFile);
      if (imageFile) form.set("image", imageFile);
      if (character) {
        form.set("character_id", String(character.id));
        if (kind === "i2v") form.set("character_view", characterView);
      }
      form.set("workflow", pack?.name ?? "");
      form.set("prompt", effectivePrompt);
      if (kind === "avatar") {
        form.set("text", text);
        if (ttsProvider) form.set("tts_provider_id", String(ttsProvider.id));
        if (ttsIsComfy) {
          if (ttsPack) form.set("tts_workflow", ttsPack.name);
          form.set("tts_inputs", JSON.stringify(Object.fromEntries(Object.entries(ttsExtra).filter(([, v]) => v !== ""))));
          form.set("voice", ttsExtra.voice ?? "");
        } else if (isLibraryVoice && (voiceRecordId !== "" || character?.voice_record_id)) {
          form.set("voice_record_id", String(voiceRecordId !== "" ? voiceRecordId : character?.voice_record_id));
        } else {
          form.set("voice", voiceName || character?.voice_name || "");
        }
      }
      if (provider) form.set("provider_id", String(provider.id));
      form.set("inputs", JSON.stringify(buildInputsWithAccel(extra, pack?.accel, accel)));
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
    (imageFile || character) &&
    (kind !== "motion" || videoFile) &&
    (kind !== "avatar" ||
      (text &&
        (ttsIsComfy
          ? !!ttsPack
          : isLibraryVoice
            ? voiceRecordId !== "" || !!voiceName || !!character?.voice_record_id
            : !!voiceName || !!character?.voice_name)));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind={kind === "avatar" ? "avatar" : kind === "motion" ? "motion" : "i2v"} icon={kind === "avatar" ? UserRound : kind === "motion" ? PersonStanding : Film} title={tx(cfg.title)} description={tx(cfg.description)} />
      <SplitPane
        storageKey={`video-${kind}`}
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={tx("视频服务")} hint={tx("只列出已启用、且具备 video 能力的 Provider。")}>
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
            <Field label={tx("工作流包")} hint={tx("必须与当前功能匹配，例如图生视频、数字人或动作迁移。")}>
              <WorkflowPackControl name={pack?.name} description={pack?.description}>
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
                    <option value="">{tx("无 {caps} 工作流包", { caps: cfg.packCaps.join(" / ") })}</option>
                  )}
                </select>
              </WorkflowPackControl>
            </Field>
          </div>

          {missingModels.length > 0 && (
            <p className="text-xs leading-relaxed text-amber-500">
              {tx("该工作流声明需要但服务上没有找到：{list}。请改选已有模型或先把模型文件放进对应目录。", {
                list: missingModels.join("、"),
              })}
            </p>
          )}

          {kind === "motion" && (
            <Field label={tx("参考视频")} hint={tx("动作来源，建议不超过 30 秒。")}>
              <FileDrop
                accept="video/*"
                title={tx("点击或拖拽上传参考视频")}
                subtitle={tx("建议不超过 30 秒")}
                names={videoFile ? [videoFile.name] : []}
                onSelect={(fs) => setVideoFile(fs?.[0] ?? null)}
              />
            </Field>
          )}
          <Field
            label={kind === "avatar" ? tx("人物图片") : tx("图片")}
            hint={
              kind === "i2v"
                ? tx("作为视频首帧。选了角色时用该视角的单人图。")
                : kind === "avatar"
                  ? tx("口播人物图。选了角色时用定妆照右侧的面部半身特写。")
                  : tx("目标人物。选了角色时用正面、侧面、背面三张全身图。")
            }
          >
            <select
              className={`${selectClass} mb-2`}
              value={characterId}
              onChange={(e) => setCharacterId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">{tx("从角色库选择，或在下面上传")}</option>
              {characters?.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            {kind === "i2v" && character && (
              <select className={`${selectClass} mb-2`} value={characterView} onChange={(e) => setCharacterView(e.target.value)}>
                <option value="portrait">{tx("面部半身特写")}</option>
                <option value="front">{tx("正面全身")}</option>
                <option value="side">{tx("侧面全身")}</option>
                <option value="back">{tx("背面全身")}</option>
              </select>
            )}
            <FileDrop
              accept="image/*"
              title={tx("点击或拖拽上传图片")}
              names={imageFile ? [imageFile.name] : []}
              onSelect={(fs) => setImageFile(fs?.[0] ?? null)}
            />
          </Field>

          {kind === "avatar" ? (
            <>
              <Field label={tx("口播文案")} hint={tx("先合成语音，再交给数字人工作流。")}>
                <textarea
                  className={`${areaClass} min-h-24`}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </Field>
              <Field label={tx("配音服务")} hint={tx("comfy 需先导入 tts 语音工作流包；Liber Speech 用音色库克隆；其余用服务音色列表。")}>
                <select
                  className={selectClass}
                  value={ttsProvider?.id ?? ""}
                  onChange={(e) => setTtsProviderId(Number(e.target.value))}
                >
                  {ttsProviders?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.type === "edge_tts" ? tx("{name}（本地）", { name: p.name }) : p.name}
                    </option>
                  ))}
                </select>
              </Field>
              {ttsIsComfy ? (
                <>
                  <Field label={tx("语音工作流")} hint={tx("tts 能力的工作流包，口播文本自动注入。")}>
                    <WorkflowPackControl name={ttsPack?.name} description={ttsPack?.description}>
                      <select
                        className={selectClass}
                        value={ttsPack?.name ?? ""}
                        onChange={(e) => setTtsWorkflow(e.target.value)}
                      >
                        {ttsPacks?.map((p) => (
                          <option key={p.name} value={p.name}>{p.name}</option>
                        ))}
                      </select>
                    </WorkflowPackControl>
                  </Field>
                  {ttsPack && (
                    <WorkflowInputs
                      inputs={ttsPack.inputs}
                      values={ttsExtra}
                      onChange={(k, v) => setTtsExtra((prev) => ({ ...prev, [k]: v }))}
                      exclude={["text"]}
                      providerId={ttsProvider?.id}
                    />
                  )}
                </>
              ) : isLibraryVoice ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label={tx("音色")} hint={tx("选自音色库（参考音频克隆）。不选则填写音色名。")}>
                    <select
                      className={selectClass}
                      value={voiceRecordId}
                      onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
                    >
                      <option value="">{tx("手动指定音色…")}</option>
                      {voices?.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {voiceRecordId === "" && (
                    <Field label={tx("音色名")} hint={tx("Liber Speech 用语言代码，例如 zh、en。")}>
                      <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
                    </Field>
                  )}
                </div>
              ) : (
                <Field label={tx("音色")} hint={tx("来自所选服务的音色列表；服务提供方页可拉取/刷新模型列表。")}>
                  {serviceVoices.length > 0 ? (
                    <select
                      className={selectClass}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    >
                      <option value="">{tx("选择音色…")}</option>
                      {voiceName && !serviceVoices.includes(voiceName) && (
                        <option value={voiceName}>{voiceName}{tx("（不在列表中）")}</option>
                      )}
                      {serviceVoices.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder={tx("如 zh-CN-XiaoxiaoNeural（列表为空时可到服务提供方页拉取模型）")}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    />
                  )}
                </Field>
              )}
            </>
          ) : (
            <PromptField
              label={tx("提示词")}
              hint={tx("描述希望画面如何运动或变化。")}
              value={promptValue}
              onChange={setPromptValue}
              jobScope={`video-${kind}:prompt-opt`}
              task={kind === "motion" ? "motion" : "i2v"}
              workflow={pack?.name}
              placeholder={tx("例如：缓慢推近，微风吹动发丝，环境音轻柔")}
            />
          )}

          {pack && hasAccel(pack.accel) && pack.accel && (
            <AccelControl
              accel={pack.accel}
              providerId={provider?.id}
              value={accel}
              onChange={setAccel}
              onApplyPreset={(preset) =>
                setExtra((prev) => {
                  const next = { ...prev };
                  for (const [k, v] of Object.entries(preset)) {
                    if (next[k] == null || next[k] === "") next[k] = v;
                  }
                  return next;
                })
              }
            />
          )}

          {pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={["prompt", "image", "video", "audio"]}
              providerId={provider?.id}
              fps={pack.fps}
            />
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? tx("生成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始生成")}
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
            emptyHint={tx("上传素材，生成第一段视频")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              { label: tx("工作流"), value: pack?.name ?? "" },
              {
                label:
                  kind === "avatar"
                    ? tx("文案")
                    : promptValue.useOptimized && promptValue.optimized.trim()
                      ? tx("提示词（已优化）")
                      : tx("提示词"),
                value: kind === "avatar" ? text : effectivePrompt,
              },
            ]}
          />
        }
      />
    </div>
  );
}

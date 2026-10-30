import { Film, PersonStanding, RefreshCw, UserRound } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, type JobOut } from "@/api/client";
import { enabledModels } from "@/lib/modelCatalog";
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
import {
  SpeechLanguageSelect,
  isLanguageCodeVoice,
  partitionServiceNames,
  sanitizeServiceVoice,
  speechLanguage,
  useDefaultSpeechModel,
} from "@/components/SpeechLanguageSelect";
import { supportsTtsPreview, TtsPreview } from "@/components/TtsPreview";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { useTx } from "@/i18n/tx";
import { CHARACTER_VIEWS, characterPromptContext } from "@/lib/characterPrompt";

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
    description: "参考视频 + 目标图片 + 提示词 → motion 工作流。时长跟随参考视频，超过约 15 秒会自动分段衔接。",
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
  const isArk = provider?.type === "volcengine_ark" && kind === "i2v";
  const arkModels = [
    ...enabledModels(provider, "t2v"),
    ...enabledModels(provider, "i2v_first"),
    ...enabledModels(provider, "i2v_flf"),
    ...enabledModels(provider, "v2v_ref"),
  ];
  const uniqueArk = [...new Map(arkModels.map((item) => [item.id, item])).values()];
  const [arkModel, setArkModel] = usePersistentState(`video-${kind}:ark-model`, "");
  const [arkSub, setArkSub] = usePersistentState(`video-${kind}:ark-sub`, "i2v_first");
  const selectedArk = uniqueArk.find((item) => item.id === arkModel) ?? uniqueArk[0];

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
  const [imageFile2, setImageFile2] = useState<File | null>(null);
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
  const [speechLang, setSpeechLang] = usePersistentState(`video-${kind}:speech-lang`, "zh");
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
  const speechModel = useDefaultSpeechModel();
  const isLibraryVoice = ttsProvider?.type === "liber_speech" || ttsProvider == null;
  const isOpenAiTts = ttsProvider?.type === "openai_tts";
  const serviceVoices = isLibraryVoice || ttsIsComfy
    ? []
    : isOpenAiTts
      ? partitionServiceNames(ttsProvider?.models ?? []).voices
      : (ttsProvider?.models ?? []);
  const queryClient = useQueryClient();
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  const [ttsWorkflow, setTtsWorkflow] = usePersistentState(`video-${kind}:tts-workflow`, "");
  const ttsPack = ttsPacks?.find((p) => p.name === ttsWorkflow) ?? ttsPacks?.[0];
  const [ttsExtra, setTtsExtra] = usePersistentState<Record<string, string>>(`video-${kind}:tts-extra`, {});
  const [error, setError] = useState<string | null>(null);
  const { data: bgmList } = useQuery({ queryKey: ["bgm"], queryFn: api.listBgm });
  const [bgmName, setBgmName] = usePersistentState(`video-${kind}:bgm-name`, "");
  const [bgmVolume, setBgmVolume] = usePersistentState(`video-${kind}:bgm-volume`, "0.2");
  const [audioMode, setAudioMode] = usePersistentState<"model" | "reference">("video-motion:audio-mode", "model");

  useEffect(() => {
    if (kind !== "avatar" || !ttsProvider || ttsIsComfy || isLibraryVoice) return;
    if (ttsProvider.models.length === 0 && !refreshModels.isPending) {
      refreshModels.mutate(ttsProvider.id);
    }
    if (ttsProvider.type === "edge_tts" || ttsProvider.type === "openai_tts") {
      const next = sanitizeServiceVoice(voiceName, serviceVoices, ttsProvider.type);
      if (next !== voiceName) setVoiceName(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, ttsProvider?.id, ttsProvider?.type, ttsIsComfy, isLibraryVoice, serviceVoices.join("|")]);

  const { job, setJobId } = useTrackedJob(`video-${kind}`);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (kind === "motion" && videoFile) form.set("video", videoFile);
      if (imageFile) form.set("image", imageFile);
      if (kind === "i2v" && pack?.inputs.image_2 && imageFile2) form.set("image_2", imageFile2);
      if (character) {
        form.set("character_id", String(character.id));
        if (kind === "i2v") form.set("character_view", characterView);
        if ((kind === "avatar" || kind === "motion") && characterView === "turnaround") {
          form.set("character_view", "turnaround");
        }
      }
      form.set("workflow", isArk ? "" : (pack?.name ?? ""));
      if (isArk && selectedArk) {
        form.set("model", selectedArk.id);
        form.set("sub_capability", arkSub);
      }
      form.set("prompt", effectivePrompt);
      if (kind === "avatar") {
        form.set("text", text);
        if (ttsProvider) form.set("tts_provider_id", String(ttsProvider.id));
        if (ttsIsComfy) {
          if (ttsPack) form.set("tts_workflow", ttsPack.name);
          form.set("tts_inputs", JSON.stringify(Object.fromEntries(Object.entries(ttsExtra).filter(([, v]) => v !== ""))));
          form.set("voice", ttsExtra.voice ?? "");
        } else if (isOpenAiTts && voiceRecordId !== "") {
          form.set("voice_record_id", String(voiceRecordId));
        } else if (isLibraryVoice && (voiceRecordId !== "" || character?.voice_record_id)) {
          form.set("voice_record_id", String(voiceRecordId !== "" ? voiceRecordId : character?.voice_record_id));
        } else if (isLibraryVoice) {
          form.set("voice", speechLanguage(speechLang, speechModel));
        } else {
          const saved = character?.voice_name && !isLanguageCodeVoice(character.voice_name) ? character.voice_name : "";
          form.set("voice", voiceName || saved);
        }
        if (isLibraryVoice && !ttsIsComfy) {
          form.set("language", speechLanguage(speechLang, speechModel));
        }
      }
      if (provider) form.set("provider_id", String(provider.id));
      if (kind === "motion") form.set("audio_mode", audioMode);
      if (bgmName) {
        form.set("bgm_path", `bgm/${bgmName}`);
        form.set("bgm_volume", bgmVolume || "0.2");
      }
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
  const advancedSummary = [
    hasAccel(pack?.accel) && accel.enabled ? tx("加速已开") : "",
    bgmName ? tx("已选背景音乐") : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const ready =
    pack &&
    (imageFile || character) &&
    (kind !== "motion" || videoFile) &&
    (kind !== "avatar" ||
      (text &&
        (ttsIsComfy
          ? !!ttsPack
          : isLibraryVoice || (isOpenAiTts && voiceRecordId !== "") || !!voiceName || !!character?.voice_name)));

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
            {isArk ? (
              <>
                <Field label={tx("模型")} hint={tx("只列出已启用、且支持视频的模型。")}>
                  <select className={selectClass} value={selectedArk?.id ?? ""} onChange={(e) => setArkModel(e.target.value)}>
                    {uniqueArk.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label={tx("能力")}>
                  <select className={selectClass} value={arkSub} onChange={(e) => setArkSub(e.target.value)}>
                    {(selectedArk?.sub_capabilities ?? ["i2v_first"]).filter((sub) => ["t2v", "i2v_first", "i2v_flf", "v2v_ref"].includes(sub)).map((sub) => (
                      <option key={sub} value={sub}>{sub}</option>
                    ))}
                  </select>
                </Field>
              </>
            ) : (
            <Field label={tx("工作流包")} hint={tx("必须与当前功能匹配，例如图生视频、数字人或动作迁移。")}>
              <WorkflowPackControl name={pack?.name} description={pack?.description}>
                {packs?.length ? (
                  <PackSelect
                    packs={packs}
                    value={pack?.name ?? ""}
                    onChange={setWorkflow}
                    ariaLabel={tx("工作流包")}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {tx("无 {caps} 工作流包", { caps: cfg.packCaps.join(" / ") })}
                  </p>
                )}
              </WorkflowPackControl>
            </Field>
            )}
          </div>

          {missingModels.length > 0 && (
            <p className="text-xs leading-relaxed text-warning">
              {tx("该工作流声明需要但服务上没有找到：{list}。请改选已有模型或先把模型文件放进对应目录。", {
                list: missingModels.join("、"),
              })}
            </p>
          )}

          {kind === "motion" && (
            <Field label={tx("参考视频")} hint={tx("动作来源。画面时长跟随参考视频，超过约 15 秒会自动分段衔接。")}>
              <FileDrop
                accept="video/*"
                title={tx("点击或拖拽上传参考视频")}
                subtitle={tx("超过约 15 秒会自动分段")}
                names={videoFile ? [videoFile.name] : []}
                onSelect={(fs) => setVideoFile(fs?.[0] ?? null)}
              />
            </Field>
          )}
          <Field
            label={
              kind === "i2v" && pack?.inputs.image?.label
                ? tx(pack.inputs.image.label)
                : kind === "avatar"
                  ? tx("人物图片")
                  : tx("图片")
            }
            hint={
              kind === "i2v"
                ? tx(pack?.inputs.image?.description || "作为视频首帧。单槽工作流只送所选视角；多槽时第一张是入镜视角，其余补还没用到的全身图。")
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
                {CHARACTER_VIEWS.map(([key, label]) => (
                  <option key={key} value={key}>{tx(label)}</option>
                ))}
              </select>
            )}
            {kind === "avatar" && character && (
              <select
                className={`${selectClass} mb-2`}
                value={characterView === "turnaround" ? "turnaround" : "portrait"}
                onChange={(e) => setCharacterView(e.target.value)}
              >
                <option value="portrait">{tx("面部半身特写")}</option>
                <option value="turnaround">{tx("定妆照")}</option>
              </select>
            )}
            {kind === "motion" && character && (
              <select
                className={`${selectClass} mb-2`}
                value={characterView === "turnaround" ? "turnaround" : "front"}
                onChange={(e) => setCharacterView(e.target.value)}
              >
                <option value="front">{tx("正面、侧面、背面三张全身图")}</option>
                <option value="turnaround">{tx("定妆照")}</option>
              </select>
            )}
            <FileDrop
              accept="image/*"
              title={tx("点击或拖拽上传图片")}
              names={imageFile ? [imageFile.name] : []}
              onSelect={(fs) => setImageFile(fs?.[0] ?? null)}
            />
          </Field>
          {kind === "i2v" && pack?.inputs.image_2 && (
            <Field
              label={tx(pack.inputs.image_2.label || "结束画面")}
              hint={tx(pack.inputs.image_2.description || "可选。不传则与首帧同一张。")}
            >
              <FileDrop
                accept="image/*"
                title={tx("可选。不传则与首帧同一张")}
                names={imageFile2 ? [imageFile2.name] : []}
                onSelect={(fs) => setImageFile2(fs?.[0] ?? null)}
              />
            </Field>
          )}

          {kind === "avatar" ? (
            <>
              <Field
                label={tx("口播文案")}
                hint={tx("画面时长跟着配音走。超过单段上限会按句子分段，用上一段尾帧接下一段，最后合成一条视频。")}
              >
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
                      <PackSelect
                        packs={ttsPacks}
                        value={ttsPack?.name ?? ""}
                        onChange={setTtsWorkflow}
                        ariaLabel={tx("语音工作流")}
                      />
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
                  <Field label={tx("音色")} hint={tx("选自音色库会克隆这条参考音频。不选则用模型自带的默认声音。")}>
                    <select
                      className={selectClass}
                      value={voiceRecordId}
                      onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
                    >
                      <option value="">{tx("使用默认声音…")}</option>
                      {voices?.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <SpeechLanguageSelect value={speechLang} onChange={setSpeechLang} model={speechModel} />
                </div>
              ) : (
                <>
                {isOpenAiTts && (
                  <Field label={tx("音色记录")} hint={tx("选自音色库时使用其中的 voice_id。不选则在下面填写音色名。")}>
                    <select
                      className={selectClass}
                      value={voiceRecordId}
                      onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
                    >
                      <option value="">{tx("手动指定音色…")}</option>
                      {voices?.filter((item) => item.voice_id).map((v) => (
                        <option key={v.id} value={v.id}>{v.name}</option>
                      ))}
                    </select>
                  </Field>
                )}
                {(!isOpenAiTts || voiceRecordId === "") && (
                <Field label={tx("音色")} hint={tx("来自所选服务的音色列表；点右侧按钮从服务拉取，也可直接输入。")}>
                  <div className="flex gap-2">
                  {serviceVoices.length > 0 ? (
                    <select
                      className={selectClass}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    >
                      <option value="">{tx("选择音色…")}</option>
                      {voiceName && !isLanguageCodeVoice(voiceName) && !serviceVoices.includes(voiceName) && (
                        <option value={voiceName}>{voiceName}</option>
                      )}
                      {serviceVoices.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder={refreshModels.isPending ? tx("正在从服务拉取音色…") : tx("拉取失败时可手动输入，如 zh-CN-XiaoxiaoNeural")}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    />
                  )}
                  <Button
                    variant="outline"
                    size="icon"
                    title={tx("从服务拉取音色列表")}
                    disabled={!ttsProvider || refreshModels.isPending}
                    onClick={() => ttsProvider && refreshModels.mutate(ttsProvider.id)}
                  >
                    <RefreshCw />
                  </Button>
                  </div>
                </Field>
                )}
                </>
              )}
              {supportsTtsPreview(ttsProvider?.type) && ttsProvider && (
                <TtsPreview providerId={ttsProvider.id} voice={voiceName || character?.voice_name || ""} />
              )}
            </>
          ) : (
            <PromptField
              label={tx("提示词")}
              hint={tx(pack?.inputs.prompt?.description || "描述希望画面如何运动或变化。")}
              value={promptValue}
              onChange={setPromptValue}
              jobScope={`video-${kind}:prompt-opt`}
              task={kind === "motion" ? "motion" : "i2v"}
              workflow={pack?.name}
              extraContext={
                character
                  ? characterPromptContext(
                      character.name,
                      character.description,
                      kind === "motion" && characterView !== "turnaround" ? "front" : characterView,
                      kind === "motion" && characterView !== "turnaround",
                    )
                  : undefined
              }
              placeholder={tx("例如：缓慢推近，微风吹动发丝，环境音轻柔")}
            />
          )}

          <AdvancedPanel summary={advancedSummary || tx("采样、配乐与权重")}>
            {pack && hasAccel(pack.accel) && pack.accel && (
              <AccelControl
                accel={pack.accel}
                providerId={provider?.id}
                value={accel}
                onChange={setAccel}
                inputs={pack.inputs}
                onApplyPreset={(patch) => setExtra((prev) => ({ ...prev, ...patch }))}
              />
            )}
            {kind === "motion" && (
              <Field label={tx("声音来源")} hint={tx("模型生成是画面自带的声音。参考视频原声会换成上传视频里的整条音轨。")}>
                <Segmented
                  ariaLabel={tx("声音来源")}
                  value={audioMode}
                  onChange={setAudioMode}
                  options={[
                    { value: "model", label: tx("模型生成") },
                    { value: "reference", label: tx("参考视频原声") },
                  ]}
                />
              </Field>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("背景音乐")} hint={tx("可选。从音乐库选择，叠在当前声音上面。")}>
                <select className={selectClass} value={bgmName} onChange={(e) => setBgmName(e.target.value)}>
                  <option value="">{tx("无背景音乐")}</option>
                  {bgmList?.map((item) => (
                    <option key={item.name} value={item.name}>{item.name}</option>
                  ))}
                </select>
              </Field>
              <Field label={tx("BGM 音量")} hint={tx("0 到 1，建议 0.1 到 0.3。")}>
                <Input type="number" min={0} max={1} step={0.05} value={bgmVolume} onChange={(e) => setBgmVolume(e.target.value)} />
              </Field>
            </div>
            {pack && (
              <WorkflowInputs
                inputs={pack.inputs}
                values={extra}
                onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
                exclude={
                  kind === "avatar" || kind === "motion"
                    ? ["prompt", "image", "video", "audio", "length", "frames"]
                    : ["prompt", "image", "video", "audio"]
                }
                providerId={provider?.id}
                fps={pack.fps}
              />
            )}
          </AdvancedPanel>
        </CardContent>
      </Card>
        }
        footer={
          <div className="flex flex-col gap-2">
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? tx("生成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始生成")}
            </Button>
          </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            jobKind={`video.${kind}`}
            emptyHint={tx(
              kind === "avatar"
                ? "上传人物图片并填写口播文案，生成数字人视频"
                : kind === "motion"
                  ? "上传参考视频与目标人物图片，生成动作迁移视频"
                  : "上传首帧图片并填写提示词，生成图生视频",
            )}
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

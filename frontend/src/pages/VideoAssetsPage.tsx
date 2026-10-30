import { Images, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { workflowPromptPlaceholder } from "@/lib/promptPlaceholder";
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
import {
  SpeechLanguageSelect,
  isLanguageCodeVoice,
  partitionServiceNames,
  sanitizeServiceVoice,
  serviceVoiceOption,
  speechLanguage,
  useDefaultSpeechModel,
} from "@/components/SpeechLanguageSelect";
import { supportsTtsPreview, TtsPreview } from "@/components/TtsPreview";
import { Button, submitButtonClass } from "@/components/ui/button";
import { SearchSelect } from "@/components/ui/search-select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { formatStepName } from "@/lib/utils";
import { Film, X } from "lucide-react";
import { useTx } from "@/i18n/tx";

const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp)$/i;

function pickAnalysisPack<T extends { name: string }>(
  packs: T[] | undefined,
  stored: string,
  kind: "image" | "video",
): T | undefined {
  return (
    packs?.find((p) => p.name === stored) ??
    packs?.find((p) => p.name.includes(kind)) ??
    packs?.[0]
  );
}

/** 自定义素材：图片/视频素材 + 文案/主题 → 配音字幕短片。支持素材动画（i2v）与背景音乐。 */
export function VideoAssetsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const enabled = providers?.filter((p) => p.enabled);
  const llmProviders = enabled?.filter((p) => p.capabilities.includes("llm"));
  const videoProviders = enabled?.filter((p) => p.capabilities.includes("video"));
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const hasLlm =
    (llmProviders?.length ?? 0) > 0 ||
    (prefs?.default_llm_provider_id != null && prefs.default_llm_provider_id > 0);
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });
  const { data: bgmList } = useQuery({ queryKey: ["bgm"], queryFn: api.listBgm });

  // ---- ① 素材 ----
  const [files, setFiles] = useState<File[]>([]);
  const fileKey = (f: File) => `${f.name}:${f.size}:${f.lastModified}`;
  const addFiles = (list: FileList | null) => {
    if (!list?.length) return;
    // FileList 是活引用，先同步快照（onChange 随后可能清空 input）
    const incoming = Array.from(list);
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey));
      const next = [...prev];
      for (const f of incoming) {
        if (!seen.has(fileKey(f))) {
          seen.add(fileKey(f));
          next.push(f);
        }
      }
      return next;
    });
  };
  const removeFile = (i: number) => setFiles((prev) => prev.filter((_, j) => j !== i));
  const previews = useMemo(
    () => files.map((f) => (IMAGE_EXT.test(f.name) ? URL.createObjectURL(f) : null)),
    [files],
  );
  useEffect(() => () => previews.forEach((u) => u && URL.revokeObjectURL(u)), [previews]);
  const hasImage = files.some((f) => IMAGE_EXT.test(f.name));
  const hasVideo = files.some((f) => !IMAGE_EXT.test(f.name));

  // ---- ② 素材分析（可选：视觉模型逐素材产出内容描述，喂给写文案的 LLM）----
  const { data: analysisPacks } = useQuery({
    queryKey: ["workflows", "analysis"],
    queryFn: () => api.listWorkflows("analysis"),
  });
  const comfyProviders = enabled?.filter((p) => p.type === "comfyui");
  const [analysisProviderId, setAnalysisProviderId] = usePersistentState<number | "">("video-assets:analysis-provider", "");
  const analysisProvider = comfyProviders?.find((p) => p.id === analysisProviderId) ?? comfyProviders?.[0];
  const [analysisImageWorkflow, setAnalysisImageWorkflow] = usePersistentState("video-assets:analysis-image-workflow", "");
  const [analysisVideoWorkflow, setAnalysisVideoWorkflow] = usePersistentState("video-assets:analysis-video-workflow", "");
  const analysisImagePack = pickAnalysisPack(analysisPacks, analysisImageWorkflow, "image");
  const analysisVideoPack = pickAnalysisPack(analysisPacks, analysisVideoWorkflow, "video");
  const [analysisExtra, setAnalysisExtra] = usePersistentState<Record<string, string>>("video-assets:analysis-extra", {});

  // ---- ③ 文案与标题 ----
  const [mode, setMode] = usePersistentState<"script" | "topic" | "analysis">("video-assets:mode", "script");
  const [script, setScript] = usePersistentState("video-assets:script", "");
  const [analysisScript, setAnalysisScript] = usePersistentState("video-assets:analysis-script", "");
  const [analysisHint, setAnalysisHint] = usePersistentState("video-assets:analysis-hint", "");
  const [topicValue, setTopicValue] = usePersistentPromptValue("video-assets:topic");
  const effectiveTopic = resolveEffectivePrompt(topicValue);
  const [title, setTitle] = usePersistentState("video-assets:title", "");
  const [duration, setDuration] = usePersistentState("video-assets:duration", 30);
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  // ---- ③ 素材动画（静态图片 → i2v 动起来）----
  const [animate, setAnimate] = usePersistentState("video-assets:animate", false);
  const [audioMode, setAudioMode] = usePersistentState<"custom" | "auto">("video-assets:audio-mode", "custom");
  const [animatePrompt, setAnimatePrompt] = usePersistentPromptValue("video-assets:animate-prompt");
  const [videoProviderId, setVideoProviderId] = usePersistentState<number | "">("video-assets:video-provider", "");
  const videoProvider = videoProviders?.find((p) => p.id === videoProviderId) ?? videoProviders?.[0];
  const { data: i2vPacks } = useQuery({
    queryKey: ["workflows", "i2v"],
    queryFn: () => api.listWorkflows("i2v"),
    enabled: animate,
  });
  const [videoWorkflow, setVideoWorkflow] = usePersistentState("video-assets:video-workflow", "");
  const videoPack = i2vPacks?.find((p) => p.name === videoWorkflow) ?? i2vPacks?.[0];
  const [videoExtra, setVideoExtra] = usePersistentState<Record<string, string>>(
    `video-assets:video-extra:${videoPack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(videoPack?.inputs, ["prompt", "image", "width", "height", "length", "seed"]),
  );
  const [videoAccel, setVideoAccel] = usePersistentState<AccelState>(
    `video-assets:accel:${videoPack?.name ?? "none"}`,
    () => defaultAccelState(videoPack?.accel),
  );

  // ---- ④ 配音 ----
  const { data: ttsPacks } = useQuery({
    queryKey: ["workflows", "tts"],
    queryFn: () => api.listWorkflows("tts"),
  });
  // 配音服务列表 = 本机/第三方 TTS Provider +（仅当存在 tts 工作流包时）Comfy
  // comfy 是工作流驱动的，没有语音包就不具备可用能力，不列出
  const ttsProviders = enabled?.filter((p) => {
    if (!p.capabilities.includes("tts")) return false;
    if (p.type === "comfyui") return (ttsPacks?.length ?? 0) > 0;
    return true;
  });
  const [ttsProviderId, setTtsProviderId] = usePersistentState<number | "">("video-assets:tts-provider", "");
  const ttsProvider =
    ttsProviders?.find((p) => p.id === ttsProviderId) ??
    ttsProviders?.find((p) => p.type === "edge_tts") ??
    ttsProviders?.[0];
  const ttsIsComfy = ttsProvider?.type === "comfyui";
  const [ttsWorkflow, setTtsWorkflow] = usePersistentState("video-assets:tts-workflow", "");
  const ttsPack = ttsPacks?.find((p) => p.name === ttsWorkflow) ?? ttsPacks?.[0];
  const [ttsExtra, setTtsExtra] = usePersistentState<Record<string, string>>("video-assets:tts-extra", {});
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("video-assets:voice-record", "");
  const [voiceName, setVoiceName] = usePersistentState("video-assets:voice-name", "");
  const [speechLang, setSpeechLang] = usePersistentState("video-assets:speech-lang", "zh");
  /** 克隆服务（Liber Speech）用音色库；其余服务（edge_tts / 第三方 TTS）用服务自己的音色列表 */
  const speechModel = useDefaultSpeechModel();
  const isLibraryVoice = ttsProvider?.type === "liber_speech" || ttsProvider == null;
  const isOpenAiTts = ttsProvider?.type === "openai_tts";
  const serviceVoices = isLibraryVoice
    ? []
    : isOpenAiTts
      ? partitionServiceNames(ttsProvider?.models ?? []).voices
      : (ttsProvider?.models ?? []);
  // 切到非克隆服务且还没拉过音色列表时自动拉一次
  useEffect(() => {
    if (ttsProvider && !ttsIsComfy && !isLibraryVoice && ttsProvider.models.length === 0 && !refreshModels.isPending) {
      refreshModels.mutate(ttsProvider.id);
    }
    if (
      ttsProvider &&
      !ttsIsComfy &&
      !isLibraryVoice &&
      (ttsProvider.type === "edge_tts" || ttsProvider.type === "openai_tts")
    ) {
      const next = sanitizeServiceVoice(voiceName, serviceVoices, ttsProvider.type);
      if (next !== voiceName) setVoiceName(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ttsProvider?.id, ttsProvider?.type, ttsIsComfy, isLibraryVoice, serviceVoices.join("|")]);

  // ---- ⑤ 画幅与背景音乐 ----
  const [aspect, setAspect] = usePersistentState("video-assets:aspect", "9:16");
  const [bgmName, setBgmName] = usePersistentState("video-assets:bgm-name", "");
  const [bgmVolume, setBgmVolume] = usePersistentState("video-assets:bgm-volume", "0.2");
  const [showSubtitle, setShowSubtitle] = usePersistentState("video-assets:show-subtitle", true);
  const [subtitleSize, setSubtitleSize] = usePersistentState("video-assets:subtitle-size", 0);
  const [subtitleColor, setSubtitleColor] = usePersistentState("video-assets:subtitle-color", "#FFFFFF");

  const [error, setError] = useState<string | null>(null);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("video-assets");
  const { job: scriptJob, setJobId: setScriptJobId } = useTrackedJob("video-assets:analysis-script");
  const appliedScriptJob = useRef<string | null>(null);
  useEffect(() => {
    if (!scriptJob || scriptJob.status !== "succeeded") return;
    if (appliedScriptJob.current === scriptJob.id) return;
    appliedScriptJob.current = scriptJob.id;
    const out = scriptJob.outputs.find((item) => item.type === "text" && item.content?.trim());
    if (out?.content) setAnalysisScript(out.content.trim());
    setScriptJobId(null);
  }, [scriptJob, setAnalysisScript, setScriptJobId]);

  const draftScript = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append("images", f);
      form.set("duration", String(duration));
      if (analysisHint.trim()) form.set("hint", analysisHint.trim());
      if (analysisProvider) form.set("analysis_provider_id", String(analysisProvider.id));
      if (hasImage && analysisImagePack) form.set("analysis_image_workflow", analysisImagePack.name);
      if (hasVideo && analysisVideoPack) form.set("analysis_video_workflow", analysisVideoPack.name);
      form.set(
        "analysis_inputs",
        JSON.stringify(Object.fromEntries(Object.entries(analysisExtra).filter(([, v]) => v !== ""))),
      );
      return api.submitVideoAssetsScript(form);
    },
    onSuccess: (j) => {
      setScriptError(null);
      setScriptJobId(j.id);
    },
    onError: (err) => setScriptError(err.message),
  });

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append("images", f);
      if (mode === "topic") form.set("topic", effectiveTopic);
      else form.set("script", mode === "analysis" ? analysisScript : script);
      if (title) form.set("title", title);
      form.set("duration", String(duration));
      form.set("aspect", aspect);
      if (!ttsIsComfy) {
        if ((isLibraryVoice || isOpenAiTts) && voiceRecordId !== "") form.set("voice_record_id", String(voiceRecordId));
        else if (isLibraryVoice) form.set("voice", speechLanguage(speechLang, speechModel));
        else form.set("voice", voiceName);
        if (isLibraryVoice) form.set("language", speechLanguage(speechLang, speechModel));
      }
      if (ttsProvider) form.set("tts_provider_id", String(ttsProvider.id));
      form.set("audio_mode", (animate && hasImage) || hasVideo ? audioMode : "custom");
      if (animate && hasImage) {
        form.set("animate", "true");
        const ap = resolveEffectivePrompt(animatePrompt);
        if (ap) form.set("animate_prompt", ap);
        if (videoProvider) form.set("video_provider_id", String(videoProvider.id));
        if (videoPack) form.set("video_workflow", videoPack.name);
        form.set("video_inputs", JSON.stringify(buildInputsWithAccel(videoExtra, videoPack?.accel, videoAccel)));
      }
      if (ttsIsComfy && ttsPack) {
        form.set("tts_workflow", ttsPack.name);
        form.set("tts_inputs", JSON.stringify(Object.fromEntries(Object.entries(ttsExtra).filter(([, v]) => v !== ""))));
      }
      if (bgmName) {
        form.set("bgm_path", `bgm/${bgmName}`);
        form.set("bgm_volume", bgmVolume || "0.2");
      }
      form.set("show_subtitle", showSubtitle ? "true" : "false");
      form.set("subtitle_size", String(subtitleSize));
      form.set("subtitle_color", subtitleColor);
      return api.submitVideoAssets(form);
    },
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const scriptRunning =
    draftScript.isPending ||
    (scriptJob != null && (scriptJob.status === "pending" || scriptJob.status === "running"));
  const canDraft =
    files.length > 0 &&
    hasLlm &&
    !scriptRunning &&
    !!analysisProvider &&
    (!hasImage || !!analysisImagePack) &&
    (!hasVideo || !!analysisVideoPack);
  const copyReady =
    mode === "script" ? script.trim() : mode === "topic" ? effectiveTopic : analysisScript.trim();
  const nativeAudio = audioMode === "auto" && ((animate && hasImage) || hasVideo);
  const ready =
    files.length > 0 &&
    copyReady &&
    (mode === "script" || hasLlm) &&
    (nativeAudio || (ttsIsComfy ? !!ttsPack : isLibraryVoice || (isOpenAiTts && voiceRecordId !== "") || !!voiceName)) &&
    (!animate || !hasImage || !!videoPack);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="clips" icon={Images} title={tx("自定义素材")} description={tx("上传图片或视频素材，配旁白和字幕后拼成短片，支持标题卡、素材动画与背景音乐。")} />
      <SplitPane
        storageKey="video-assets"
        left={
      <div className="flex flex-col gap-4">
      {/* ① 素材 */}
      <Card>
        <CardHeader>
          <CardTitle>{tx("素材")}</CardTitle>
          <CardDescription>{tx("图片和视频都可以，顺序即分镜顺序。视频素材会循环/截断对齐配音时长。")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Field label={tx("素材文件")} hint={tx("支持 JPG/PNG/WebP/GIF 图片和 MP4/MOV/AVI/WebM 视频，可分多次添加。")}>
            <FileDrop
              accept="image/*,video/*"
              multiple
              clearAfterSelect
              title={tx("点击或拖拽上传素材")}
              subtitle={tx("图片与视频，支持多选、多次添加")}
              onSelect={addFiles}
            />
          </Field>
          {files.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {files.map((f, i) => (
                <div key={fileKey(f)} className="group relative size-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted">
                  {previews[i] ? (
                    <img src={previews[i]!} alt={f.name} className="size-full object-cover" />
                  ) : (
                    <span className="grid size-full place-items-center text-muted-foreground">
                      <Film className="size-6" />
                    </span>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[10px] leading-none text-white">
                    {i + 1}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    title={tx("移除 {name}", { name: f.name })}
                    className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-danger group-hover:opacity-100"
                  >
                    <X className="size-3" />
                  </button>
                  <span className="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-[10px] leading-none text-white">
                    {f.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ② 文案与标题 */}
      <Card>
        <CardHeader>
          <CardTitle>{tx("文案与标题")}</CardTitle>
          <CardDescription>
            {tx("标题会作为 2 秒标题卡放在片头。自备文案和主题生成都不看画面；看素材写会先生成一段可改的口播。")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label={tx("视频标题")} hint={tx("选填。留空则没有标题卡。")}>
            <Input placeholder={tx("例如：宠物店年终大促")} value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="overflow-x-auto">
            <Segmented
              ariaLabel={tx("文案来源")}
              options={[
                { value: "script", label: tx("自备文案（按行对应素材）") },
                { value: "topic", label: tx("主题生成文案") },
                { value: "analysis", label: tx("看素材写文案") },
              ]}
              value={mode}
              onChange={setMode}
            />
          </div>
          {mode === "script" ? (
            <Field label={tx("口播文案")} hint={tx("每行一句，行数建议与素材数量一致；不够会循环使用。")}>
              <textarea
                className={`${areaClass} min-h-24`}
                value={script}
                onChange={(e) => setScript(e.target.value)}
              />
            </Field>
          ) : mode === "topic" ? (
            <>
              {!hasLlm && (
                <p className="text-sm text-warning">
                  尚未配置 LLM。请到{" "}
                  <Link className="underline" to="/settings/system">
                    {tx('系统设置')}
                  </Link>{" "}
                  {tx('或「服务提供方」添加。')}
                </p>
              )}
              <PromptField
                label={tx("主题")}
                hint={tx("AI 按文件名和目标时长写口播，不看画面内容。脚本 LLM 使用系统设置中的默认服务。")}
                value={topicValue}
                onChange={setTopicValue}
                jobScope="video-assets:topic-opt"
                task="assets_topic"
                aspect={aspect}
                placeholder={tx("例如：宠物店年终大促，语气热情")}
              />
              <Field label={tx("目标时长（秒）")} hint={tx("AI 按它控制文案长度，5 到 600。")}>
                <NumberStepper ariaLabel={tx("目标时长")} min={5} max={600} step={5} value={duration} onChange={setDuration} />
              </Field>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                {tx("先看每张图、每段视频里实际是什么，再写成口播。生成后可以改，出片时用这段文字。")}
              </p>
              {!hasLlm && (
                <p className="text-sm text-warning">
                  尚未配置 LLM。请到{" "}
                  <Link className="underline" to="/settings/system">
                    {tx("系统设置")}
                  </Link>{" "}
                  {tx("或「服务提供方」添加。")}
                </p>
              )}
              {comfyProviders && comfyProviders.length === 0 && (
                <p className="text-sm text-warning">
                  {tx("还没有 ComfyUI 服务。请到「服务提供方」添加后再生成文案。")}
                </p>
              )}
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label={tx("分析服务")} hint={tx("执行分析工作流的 ComfyUI。")}>
                  <select
                    className={selectClass}
                    value={analysisProvider?.id ?? ""}
                    onChange={(e) => setAnalysisProviderId(Number(e.target.value))}
                  >
                    {comfyProviders?.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label={tx("图片分析工作流")} hint={tx("analysis 能力包，如 analysis_image_qwenvl。有图片时必选。")}>
                  <WorkflowPackControl name={analysisImagePack?.name} description={analysisImagePack?.description}>
                    <PackSelect
                      packs={analysisPacks}
                      value={analysisImagePack?.name ?? ""}
                      onChange={setAnalysisImageWorkflow}
                      ariaLabel={tx("图片分析工作流")}
                    />
                  </WorkflowPackControl>
                </Field>
                <Field label={tx("视频分析工作流")} hint={tx("有视频素材时使用，如 analysis_video_qwenvl。")}>
                  <WorkflowPackControl name={analysisVideoPack?.name} description={analysisVideoPack?.description}>
                    <PackSelect
                      packs={analysisPacks}
                      value={analysisVideoPack?.name ?? ""}
                      onChange={setAnalysisVideoWorkflow}
                      ariaLabel={tx("视频分析工作流")}
                    />
                  </WorkflowPackControl>
                </Field>
              </div>
              {analysisPacks && analysisPacks.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  {tx("没有 analysis 能力的工作流包，请到「设置 → 工作流包」导入。")}
                </p>
              )}
              {(hasImage ? analysisImagePack : analysisVideoPack) && (
                <WorkflowInputs
                  inputs={(hasImage ? analysisImagePack : analysisVideoPack)!.inputs}
                  values={analysisExtra}
                  onChange={(k, v) => setAnalysisExtra((prev) => ({ ...prev, [k]: v }))}
                  exclude={["image", "video"]}
                  providerId={analysisProvider?.id}
                />
              )}
              <Field label={tx("补充要求")} hint={tx("选填。例如语气、要强调的卖点。留空就只按画面写。")}>
                <Input
                  placeholder={tx("例如：语气热情，突出价格")}
                  value={analysisHint}
                  onChange={(e) => setAnalysisHint(e.target.value)}
                />
              </Field>
              <Field label={tx("目标时长（秒）")} hint={tx("AI 按它控制文案长度，5 到 600。")}>
                <NumberStepper ariaLabel={tx("目标时长")} min={5} max={600} step={5} value={duration} onChange={setDuration} />
              </Field>
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" disabled={!canDraft} onClick={() => draftScript.mutate()}>
                  {scriptRunning ? tx("正在看素材并写文案…") : tx("生成文案")}
                </Button>
                {scriptRunning && scriptJob?.steps.at(-1) && (
                  <span className="text-sm text-muted-foreground">
                    {formatStepName(scriptJob.steps.at(-1)!.name, tx)}
                  </span>
                )}
              </div>
              {(scriptError || (scriptJob?.status === "failed" && scriptJob.error)) && (
                <p className="text-sm text-danger">{scriptError || scriptJob?.error}</p>
              )}
              <Field label={tx("口播文案")} hint={tx("一行对应一段素材。生成后可以再改，出片用的就是这里的文字。")}>
                <textarea
                  className={`${areaClass} min-h-24`}
                  value={analysisScript}
                  placeholder={tx("点「生成文案」后出现在这里。")}
                  onChange={(e) => setAnalysisScript(e.target.value)}
                />
              </Field>
            </>
          )}
        </CardContent>
      </Card>

      {/* ③ 素材动画（常驻显示；没有图片素材时提示） */}
      <Card>
        <CardHeader>
          <CardTitle>{tx("素材动画")}</CardTitle>
          <CardDescription>
            {tx('开启后，静态图片先经 i2v 工作流动画化再合成（每张图一次图生视频，较慢）。视频素材不受影响。')}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!hasImage && (
            <p className="text-sm text-muted-foreground">{tx("当前没有图片素材。上传图片后可启用素材动画。")}</p>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={animate}
              disabled={!hasImage}
              onChange={(e) => setAnimate(e.target.checked)}
            />
            {tx('静态图片动画化（i2v）')}
          </label>
            {animate && (
              <>
                <PromptField
                  label={tx("动画提示词")}
                  hint={tx("可选。描述图片如何动起来；留空则用默认轻微推镜运动。")}
                  value={animatePrompt}
                  onChange={setAnimatePrompt}
                  jobScope="video-assets:animate-opt"
                  task="i2v"
                  workflow={videoPack?.name}
                  aspect={aspect}
                  placeholder={workflowPromptPlaceholder(tx, videoPack, { fallback: "描述镜头、运动和声音" })}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label={tx("动画服务")} hint={tx("执行 i2v 的视频 Provider。")}>
                    <select
                      className={selectClass}
                      value={videoProvider?.id ?? ""}
                      onChange={(e) => setVideoProviderId(Number(e.target.value))}
                    >
                      {videoProviders?.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label={tx("动画工作流")} hint={tx("i2v 能力的工作流包，图片作为首帧。")}>
                    <WorkflowPackControl name={videoPack?.name} description={videoPack?.description}>
                      <PackSelect
                        packs={i2vPacks}
                        value={videoPack?.name ?? ""}
                        onChange={setVideoWorkflow}
                        ariaLabel={tx("动画工作流")}
                      />
                    </WorkflowPackControl>
                  </Field>
                </div>
                {videoPack && hasAccel(videoPack.accel) && videoPack.accel && (
                  <AccelControl
                    accel={videoPack.accel}
                    providerId={videoProvider?.id}
                    value={videoAccel}
                    onChange={setVideoAccel}
                    inputs={videoPack.inputs}
                    onApplyPreset={(patch) => setVideoExtra((prev) => ({ ...prev, ...patch }))}
                  />
                )}
                {videoPack && (
                  <WorkflowInputs
                    inputs={videoPack.inputs}
                    values={videoExtra}
                    onChange={(k, v) => setVideoExtra((prev) => ({ ...prev, [k]: v }))}
                    exclude={["image", "prompt", "width", "height"]}
                    providerId={videoProvider?.id}
                    fps={videoPack.fps}
                  />
                )}
              </>
            )}
          </CardContent>
        </Card>

      {/* ⑤ 配音 */}
      <Card>
        <CardHeader>
          <CardTitle>{tx("配音")}</CardTitle>
          <CardDescription>{tx("逐素材配音：ComfyUI 语音工作流、Liber Speech 或第三方 TTS API。")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {((animate && hasImage) || hasVideo) && (
            <Field label={tx("声音来源")} hint={tx("自定义配音按文案合成。模型原声保留素材或动画自己的音轨。")}>
              <Segmented
                ariaLabel={tx("声音来源")}
                value={audioMode}
                onChange={setAudioMode}
                options={[
                  { value: "custom", label: tx("自定义配音") },
                  { value: "auto", label: tx("模型原声") },
                ]}
              />
            </Field>
          )}
          {!nativeAudio && (
          <>
          <Field label={tx("配音服务")} hint={tx("只列出已启用、且具备 tts 能力的 Provider。")}>
            <select
              className={selectClass}
              value={ttsProvider?.id ?? ""}
              onChange={(e) => setTtsProviderId(Number(e.target.value))}
            >
              {ttsProviders?.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>
          {ttsIsComfy ? (
            <>
              <Field label={tx("语音工作流")} hint={tx("tts 能力的工作流包，口播文本会自动注入。")}>
                <WorkflowPackControl name={ttsPack?.name} description={ttsPack?.description}>
                  <PackSelect
                    packs={ttsPacks}
                    value={ttsPack?.name ?? ""}
                    onChange={setTtsWorkflow}
                    ariaLabel={tx("语音工作流")}
                  />
                </WorkflowPackControl>
              </Field>
              {ttsPacks && ttsPacks.length === 0 && (
                <p className="text-sm text-muted-foreground">{tx("没有 tts 能力的工作流包，请到「设置 → 工作流包」导入。")}</p>
              )}
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
                      {v.is_default ? tx("（默认）") : ""}
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
                    <option key={v.id} value={v.id}>
                      {v.name}
                      {v.is_default ? tx("（默认）") : ""}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {(!isOpenAiTts || voiceRecordId === "") && (
            <Field label={tx("音色")} hint={tx("来自所选服务的音色列表；点右侧按钮从服务拉取，也可直接输入。")}>
              <div className="flex gap-2">
                {serviceVoices.length > 0 ? (
                  <SearchSelect
                    ariaLabel={tx("音色")}
                    value={voiceName}
                    onChange={setVoiceName}
                    placeholder={tx("搜索音色")}
                    emptyText={tx("没有匹配项")}
                    options={[
                      { value: "", label: tx("选择音色…") },
                      ...(voiceName && !isLanguageCodeVoice(voiceName) && !serviceVoices.includes(voiceName)
                        ? [serviceVoiceOption(voiceName)]
                        : []),
                      ...serviceVoices.map(serviceVoiceOption),
                    ]}
                  />
                ) : (
                  <Input
                    className="min-w-0 flex-1"
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
            <TtsPreview
              providerId={ttsProvider.id}
              voice={
                isOpenAiTts && voiceRecordId !== ""
                  ? (voices?.find((item) => item.id === voiceRecordId)?.voice_id || "")
                  : voiceName
              }
            />
          )}
          </>
          )}
        </CardContent>
      </Card>

      {/* ⑥ 画幅与背景音乐 */}
      <Card>
        <CardHeader>
          <CardTitle>{tx("画幅与背景音乐")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-3">
            <Field label={tx("画幅")} hint={tx("成片宽高比。")}>
              <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
                <option value="9:16">{tx("9:16 竖屏")}</option>
                <option value="1:1">{tx("1:1 方形")}</option>
                <option value="16:9">{tx("16:9 横屏")}</option>
              </select>
            </Field>
            <Field label={tx("背景音乐")} hint={tx("从音乐库选择；留空则只有人声。")}>
              <select className={selectClass} value={bgmName} onChange={(e) => setBgmName(e.target.value)}>
                <option value="">{tx("无背景音乐")}</option>
                {bgmList?.map((b) => (
                  <option key={b.name} value={b.name}>{b.name}</option>
                ))}
              </select>
            </Field>
            <Field label={tx("BGM 音量")} hint={tx("0 到 1，建议 0.1 到 0.3。")}>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={bgmVolume}
                onChange={(e) => setBgmVolume(e.target.value)}
              />
            </Field>
          </div>
          <div className="flex flex-col gap-3">
            <Field label={tx("视频字幕")} hint={tx("烧录在画面底部的口播字幕。关闭后成片无字幕。标题卡不烧字幕。")}>
              <label className="flex h-11 items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={showSubtitle}
                  onChange={(e) => setShowSubtitle(e.target.checked)}
                />
                {tx("烧录字幕")}
              </label>
            </Field>
            <Field label={tx("字幕字号")} hint={tx("底部字幕条的字号。0 为自动（跟随画面高度）。")}>
              <NumberStepper
                ariaLabel={tx("字幕字号")}
                min={0}
                max={64}
                value={subtitleSize}
                onChange={setSubtitleSize}
              />
            </Field>
            <Field label={tx("字幕颜色")} hint={tx("底部字幕条文字颜色，默认白色。")}>
              <input
                type="color"
                aria-label={tx("字幕颜色")}
                value={subtitleColor}
                onChange={(e) => setSubtitleColor(e.target.value.toUpperCase())}
                className="h-11 w-full cursor-pointer rounded-[10px] border border-border bg-field p-1.5"
              />
            </Field>
          </div>
        </CardContent>
      </Card>
      </div>
        }
        footer={
          <div className="flex flex-col gap-2">
            {error && <p className="text-sm text-danger">{error}</p>}
            {running && job?.steps?.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {formatStepName(String(job.steps[job.steps.length - 1]?.name ?? ""))}
              </p>
            )}
            <Button className={submitButtonClass} onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? tx("合成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始合成")}
            </Button>
          </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            jobKind="video.assets"
            emptyHint={tx("上传素材，拼成一条短片")}
            meta={[
              { label: tx("画幅"), value: aspect },
              { label: tx("标题"), value: title },
              { label: tx("内容"), value: mode === "script" ? script : effectiveTopic },
            ]}
          />
        }
      />
    </div>
  );
}

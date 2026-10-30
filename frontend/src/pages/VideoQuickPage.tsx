import { Clapperboard, FileText, Image as ImageIcon, RefreshCw, Volume2 } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api, fetchAssetBlob, TERMINAL_STATUSES, type TemplateOut } from "@/api/client";
import {
  AccelControl,
  buildInputsWithAccel,
  defaultAccelState,
  hasAccel,
  type AccelState,
} from "@/components/AccelControl";
import {
  PromptField,
  emptyPromptValue,
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
import { TemplateThumb } from "@/components/TemplateThumb";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { AdvancedPanel } from "@/components/ui/advanced-panel";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { PackSelect, WorkflowPackControl } from "@/components/WorkflowPackHint";
import { SearchSelect } from "@/components/ui/search-select";
import { modelDefaultsFromInputs } from "@/lib/workflowForm";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentPromptValue, usePersistentState } from "@/hooks/usePersistentState";
import { cn, formatStepName } from "@/lib/utils";
import { useTx } from "@/i18n/tx";
import { characterPromptContext, CHARACTER_VIEWS } from "@/lib/characterPrompt";

const ASPECTS = [
  { value: "9:16", label: "9:16 竖屏" },
  { value: "1:1", label: "1:1 方形" },
  { value: "16:9", label: "16:9 横屏" },
];

/** 三种分镜模式：画面来源不同，先选模式再选模板。 */
const TYPE_MODES: { value: string; label: string; desc: string }[] = [
  { value: "static", label: "静态样式", desc: "本地排版渲染，不跑 AI 出图，最快" },
  { value: "image", label: "生成插图", desc: "逐镜调用图像工作流生成插图" },
  { value: "video", label: "生成视频", desc: "逐镜调用视频工作流生成片段，最慢" },
];

/** 配音服务下拉显示名：edge_tts 固定为「本地」。 */
function ttsProviderLabel(
  p: { type: string; name: string },
  tx: (zh: string, vars?: Record<string, string | number>) => string,
): string {
  return p.type === "edge_tts" ? tx("本地") : p.name;
}

/** 批量任务的单行状态：3 秒轮询直到终态，成功后刷新历史作品。 */
function BatchJobRow({ topic, jobId }: { topic: string; jobId: string }) {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId),
    refetchInterval: (q) =>
      q.state.data && TERMINAL_STATUSES.includes(q.state.data.status) ? false : 3000,
  });
  useEffect(() => {
    if (job?.status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["assets", "video"] });
    }
  }, [job?.status, queryClient]);

  const statusText = !job
    ? tx("加载中…")
    : job.status === "pending"
      ? tx("排队中")
      : job.status === "running"
        ? tx("进行中… {pct}%", { pct: Math.round(job.progress * 100) })
        : job.status === "succeeded"
          ? tx("完成")
          : job.status === "failed"
            ? tx("失败：{err}", { err: job.error ?? "" })
            : tx("已取消");
  const cls =
    job?.status === "succeeded"
      ? "text-success"
      : job?.status === "failed" || job?.status === "canceled"
        ? "text-danger"
        : "text-muted-foreground";
  return (
    <div className="flex items-center gap-3 rounded-lg bg-muted/60 px-3 py-2">
      <span className="min-w-0 flex-1 truncate text-sm">{topic}</span>
      <span className={cn("shrink-0 text-xs", cls)} title={job?.error ?? undefined}>
        {statusText}
      </span>
    </div>
  );
}

/** 批量任务总览卡。 */
function BatchStatus({ jobs }: { jobs: { topic: string; jobId: string }[] }) {
  const tx = useTx();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{tx("批量任务")}</CardTitle>
        <CardDescription>{tx("每个主题一个任务，排队执行；单个失败不影响其他。")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {jobs.map((j) => (
          <BatchJobRow key={j.jobId} topic={j.topic} jobId={j.jobId} />
        ))}
      </CardContent>
    </Card>
  );
}

export function VideoQuickPage() {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const enabled = providers?.filter((p) => p.enabled);
  const llmProviders = enabled?.filter((p) => p.capabilities.includes("llm"));
  const imageProviders = enabled?.filter((p) => p.capabilities.includes("image"));
  const videoProviders = enabled?.filter((p) => p.capabilities.includes("video"));
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const hasLlm =
    (llmProviders?.length ?? 0) > 0 ||
    (prefs?.default_llm_provider_id != null && prefs.default_llm_provider_id > 0);

  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  // ---- ① 视频脚本 ----
  const [mode, setMode] = usePersistentState<"topic" | "script" | "batch">("video-quick:mode", "topic");
  const location = useLocation();
  const incomingTopic = (location.state as { prompt?: string } | null)?.prompt;
  const [topicValue, setTopicValue] = usePersistentPromptValue("video-quick:topic");
  useEffect(() => {
    if (incomingTopic) {
      setTopicValue(emptyPromptValue(incomingTopic));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const effectiveTopic = resolveEffectivePrompt(topicValue);
  /** 固定文案 + 插图/视频：原始=口播，优化后=画面提示词 */
  const [scriptVisual, setScriptVisual] = usePersistentPromptValue("video-quick:script");
  const script = scriptVisual.raw;
  const [scriptTitle, setScriptTitle] = usePersistentState("video-quick:script-title", "");
  const [splitMode, setSplitMode] = usePersistentState("video-quick:split-mode", "paragraph");
  const [count, setCount] = usePersistentState("video-quick:count", 4);
  const queryClient = useQueryClient();
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  const [storyboardOnly, setStoryboardOnly] = usePersistentState("video-quick:storyboard-only", false);
  /** AI 创作时：是否让后端 LLM 写画面提示词。与工作流包里的 Guide 无关 */
  const [optimizeVisuals, setOptimizeVisuals] = usePersistentState("video-quick:optimize-visuals", true);
  const [batchText, setBatchText] = usePersistentState("video-quick:batch-topics", "");
  const [batchJobs, setBatchJobs] = useState<{ topic: string; jobId: string }[] | null>(null);
  /** 批量主题：一行一个，去空行，上限 100 */
  const batchTopics = batchText
    .split("\n")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 100);

  // ---- ② 分镜模板 ----
  const [aspect, setAspect] = usePersistentState("video-quick:aspect", "9:16");
  const { data: templates } = useQuery({
    queryKey: ["templates", aspect],
    queryFn: () => api.listTemplates(aspect),
  });
  const usableTemplates = templates?.filter((t) => t.type !== "asset");
  const [templateName, setTemplateName] = usePersistentState("video-quick:template", "");
  const tpl: TemplateOut | undefined =
    usableTemplates?.find((t) => t.name === templateName) ??
    usableTemplates?.find((t) => t.type === "static") ??
    usableTemplates?.[0];
  const [imageProviderId, setImageProviderId] = usePersistentState<number | "">("video-quick:image-provider", "");
  const imageProvider = imageProviders?.find((p) => p.id === imageProviderId) ?? imageProviders?.[0];
  const [imageWorkflow, setImageWorkflow] = usePersistentState("video-quick:image-workflow", "");
  const { data: imagePacks } = useQuery({
    queryKey: ["workflows", "t2i"],
    queryFn: () => api.listWorkflows("t2i"),
    enabled: tpl?.type === "image" && tpl.needs_image,
  });
  const imagePack = imagePacks?.find((p) => p.name === imageWorkflow) ?? imagePacks?.[0];
  const [imageExtra, setImageExtra] = usePersistentState<Record<string, string>>(
    `video-quick:image-extra:${imagePack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(imagePack?.inputs, ["prompt", "width", "height"]),
  );
  const [imageAccel, setImageAccel] = usePersistentState<AccelState>(
    `video-quick:image-accel:${imagePack?.name ?? "none"}`,
    () => defaultAccelState(imagePack?.accel),
  );
  const [stylePrefix, setStylePrefix] = usePersistentState("video-quick:style-prefix", "");
  const [characterId, setCharacterId] = usePersistentState<number | "">("video-quick:character", "");
  const [characterView, setCharacterView] = usePersistentState("video-quick:character-view", "front");
  const { data: characters } = useQuery({ queryKey: ["characters"], queryFn: api.listCharacters });
  const character = characters?.find((item) => item.id === characterId) ?? null;
  const { data: t2vPacks } = useQuery({
    queryKey: ["workflows", "t2v"],
    queryFn: () => api.listWorkflows("t2v"),
    enabled: tpl?.type === "video",
  });
  const { data: i2vPacks } = useQuery({
    queryKey: ["workflows", "i2v"],
    queryFn: () => api.listWorkflows("i2v"),
    enabled: tpl?.type === "video" && characterId !== "",
  });
  const videoPacks = characterId !== "" ? [...(t2vPacks ?? []), ...(i2vPacks ?? [])] : t2vPacks;
  const [videoProviderId, setVideoProviderId] = usePersistentState<number | "">("video-quick:video-provider", "");
  const videoProvider = videoProviders?.find((p) => p.id === videoProviderId) ?? videoProviders?.[0];
  const [videoWorkflow, setVideoWorkflow] = usePersistentState("video-quick:video-workflow", "");
  const videoPack = videoPacks?.find((p) => p.name === videoWorkflow) ?? videoPacks?.[0];
  const [videoExtra, setVideoExtra] = usePersistentState<Record<string, string>>(
    `video-quick:video-extra:${videoPack?.name ?? "none"}`,
    () => modelDefaultsFromInputs(videoPack?.inputs, ["prompt", "width", "height", "length", "seed"]),
  );
  const [videoAccel, setVideoAccel] = usePersistentState<AccelState>(
    `video-quick:accel:${videoPack?.name ?? "none"}`,
    () => defaultAccelState(videoPack?.accel),
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  // 文字显隐与字号：模板标题/文案（倍率），视频烧录字幕（字号，0=自动）
  const [showTitle, setShowTitle] = usePersistentState("video-quick:show-title", true);
  const [showText, setShowText] = usePersistentState("video-quick:show-text", true);
  const [showSubtitle, setShowSubtitle] = usePersistentState("video-quick:show-subtitle", true);
  const [titleScale, setTitleScale] = usePersistentState("video-quick:title-scale", 1);
  const [textScale, setTextScale] = usePersistentState("video-quick:text-scale", 1);
  const [subtitleSize, setSubtitleSize] = usePersistentState("video-quick:subtitle-size", 0);
  const [subtitleColor, setSubtitleColor] = usePersistentState("video-quick:subtitle-color", "#FFFFFF");
  /** 当前模板模式（asset 不参与快速创作）；切换模式时选中该模式的第一个模板。 */
  const modeType = tpl?.type === "asset" ? "static" : (tpl?.type ?? "static");
  const switchModeType = (t: string) => {
    const first = usableTemplates?.find((x) => x.type === t);
    if (first) setTemplateName(first.name);
  };

  // ---- ③ 配音合成 ----
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

  const [audioMode, setAudioMode] = usePersistentState<"custom" | "auto">("video-quick:audio-mode", "custom");
  const [ttsProviderId, setTtsProviderId] = usePersistentState<number | "">("video-quick:tts-provider", "");
  const ttsProvider =
    ttsProviders?.find((p) => p.id === ttsProviderId) ??
    ttsProviders?.find((p) => p.type === "edge_tts") ??
    ttsProviders?.[0];
  const ttsIsComfy = ttsProvider?.type === "comfyui";
  /** 克隆服务（Liber Speech）用音色库；edge_tts / 第三方用服务自己的音色列表 */
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
  const [ttsWorkflow, setTtsWorkflow] = usePersistentState("video-quick:tts-workflow", "");
  const ttsPack = ttsPacks?.find((p) => p.name === ttsWorkflow) ?? ttsPacks?.[0];
  const [ttsExtra, setTtsExtra] = usePersistentState<Record<string, string>>("video-quick:tts-extra", {});
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("video-quick:voice-record", "");
  const [voiceName, setVoiceName] = usePersistentState("video-quick:voice-name", "");
  useEffect(() => {
    if (characterId === "" || voiceRecordId !== "") return;
    if (character?.voice_record_id) setVoiceRecordId(character.voice_record_id);
  }, [character, characterId, setVoiceRecordId, voiceRecordId]);
  const [speechLang, setSpeechLang] = usePersistentState("video-quick:speech-lang", "zh");

  // ---- ④ 背景音乐 ----
  const { data: bgmList } = useQuery({ queryKey: ["bgm"], queryFn: api.listBgm });
  const [bgmName, setBgmName] = usePersistentState("video-quick:bgm-name", "");
  const [bgmVolume, setBgmVolume] = usePersistentState("video-quick:bgm-volume", "0.2");
  const uploadBgm = useMutation({
    mutationFn: (f: File) => api.uploadBgm(f),
    onSuccess: (item) => {
      // 上传即入库，并直接选中这首
      setBgmName(item.name);
      queryClient.invalidateQueries({ queryKey: ["bgm"] });
    },
    onError: (err) => setError(err.message),
  });

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
    const needsVisualTpl = tpl?.type === "image" || tpl?.type === "video";
    // 固定文案：若右侧已有优化画面词且开关打开，前端拼 storyboard，不再让后端 LLM 二次写画面
    let board = storyboard;
    let optimize = optimizeVisuals;
    if (mode === "script" && needsVisualTpl) {
      optimize = scriptVisual.useOptimized;
      if (!board && scriptVisual.useOptimized && scriptVisual.optimized.trim()) {
        const segments = script
          .split(splitMode === "line" ? /\n+/ : splitMode === "sentence" ? /[。！？.!?]+/ : /\n\s*\n/)
          .map((s) => s.trim())
          .filter(Boolean);
        const visuals = scriptVisual.optimized
          .split(/\n+/)
          .map((s) => s.trim())
          .filter(Boolean);
        board = {
          title: scriptTitle || tx("自定义文案"),
          frames: segments.map((text, i) => ({
            text,
            visual: visuals[i] || visuals[0] || text,
          })),
        };
        optimize = false;
      }
    }
    return {
      topic: mode === "topic" ? effectiveTopic : undefined,
      script: mode === "script" ? script : undefined,
      title: mode === "script" ? scriptTitle : effectiveTopic,
      split_mode: splitMode,
      storyboard_count: count,
      aspect,
      template: tpl?.name,
      voice_record_id:
        !ttsIsComfy && (isLibraryVoice || isOpenAiTts) && voiceRecordId !== "" ? voiceRecordId : undefined,
      voice: ttsIsComfy
        ? (ttsExtra.voice ?? "")
        : (isLibraryVoice || isOpenAiTts) && voiceRecordId !== ""
          ? ""
          : isLibraryVoice
            ? speechLanguage(speechLang, speechModel)
            : voiceName,
      language: !ttsIsComfy && isLibraryVoice ? speechLanguage(speechLang, speechModel) : undefined,
      style_prefix: stylePrefix,
      character_id: characterId === "" ? undefined : characterId,
      character_view: characterView,
      storyboard: board,
      storyboard_only: storyboardOnly,
      optimize_visuals: optimize,
      tts_provider_id: ttsProvider?.id,
      image_provider_id: imageProvider?.id,
      video_provider_id: videoProvider?.id,
      tts_workflow: ttsIsComfy ? ttsPack?.name : undefined,
      tts_inputs:
        ttsIsComfy
          ? Object.fromEntries(Object.entries(ttsExtra).filter(([, v]) => v !== ""))
          : undefined,
      audio_mode: tpl?.type === "video" ? audioMode : "custom",
      video_workflow: tpl?.type === "video" ? videoPack?.name : undefined,
      video_inputs: tpl?.type === "video"
        ? buildInputsWithAccel(videoExtra, videoPack?.accel, videoAccel)
        : undefined,
      image_workflow: tpl?.type === "image" && tpl.needs_image ? imagePack?.name : undefined,
      image_inputs: tpl?.type === "image" && tpl.needs_image
        ? buildInputsWithAccel(imageExtra, imagePack?.accel, imageAccel)
        : undefined,
      bgm_path: bgmName ? `bgm/${bgmName}` : undefined,
      bgm_volume: Number(bgmVolume) || 0.2,
      show_title: showTitle,
      show_text: showText,
      show_subtitle: showSubtitle,
      title_scale: titleScale,
      text_scale: textScale,
      subtitle_size: subtitleSize,
      subtitle_color: subtitleColor,
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
        throw new Error(tx("分镜 JSON 解析失败: {err}", { err: (e as Error).message }));
      }
      return api.submitQuickVideo(await buildBody(storyboard));
    },
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  /** 批量提交：每个主题一个独立任务，共享当前模板/配音/音乐配置。 */
  const batchSubmit = useMutation({
    mutationFn: async () => {
      const shared = await buildBody();
      const results: { topic: string; jobId: string }[] = [];
      for (const t of batchTopics) {
        const j = await api.submitQuickVideo({
          ...shared,
          topic: t,
          title: t,
          script: undefined,
          storyboard: undefined,
          storyboard_only: false,
        });
        results.push({ topic: t, jobId: j.id });
      }
      return results;
    },
    onSuccess: (jobs) => {
      setError(null);
      setBatchJobs(jobs);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const needsLlm =
    mode === "topic" ||
    mode === "batch" ||
    ((tpl?.type === "image" || tpl?.type === "video") &&
      (mode === "script" ? scriptVisual.useOptimized && !scriptVisual.optimized.trim() : optimizeVisuals));
  const nativeAudio = tpl?.type === "video" && audioMode === "auto";
  const advancedSummary = [
    (tpl?.type === "image" && hasAccel(imagePack?.accel) && imageAccel.enabled) ||
    (tpl?.type === "video" && hasAccel(videoPack?.accel) && videoAccel.enabled)
      ? tx("加速已开")
      : "",
    bgmName ? tx("已选背景音乐") : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const submitDisabled =
    (mode === "topic" ? !effectiveTopic : !script.trim()) ||
    !tpl ||
    (needsLlm && !hasLlm) ||
    (!nativeAudio && !ttsIsComfy && !isLibraryVoice && !(isOpenAiTts && voiceRecordId !== "") && !voiceName) ||
    (!nativeAudio && ttsIsComfy && !ttsPack) ||
    (tpl?.type === "video" && !videoPacks?.length) ||
    submit.isPending ||
    !!running;
  const batchDisabled =
    batchTopics.length === 0 ||
    !tpl ||
    !hasLlm ||
    (!nativeAudio && !ttsIsComfy && !isLibraryVoice && !(isOpenAiTts && voiceRecordId !== "") && !voiceName) ||
    (!nativeAudio && ttsIsComfy && !ttsPack) ||
    (tpl?.type === "video" && !videoPacks?.length) ||
    batchSubmit.isPending;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="video" icon={Clapperboard} title={tx("快速创作")} description={tx("一句话出短视频：文案、分镜、配音、字幕和拼接。")} />
      <SplitPane
        storageKey="video-quick"
        left={
      <div className="flex flex-col gap-4">
      {/* ① 视频脚本 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><FileText className="size-4" />{tx("视频脚本")}</CardTitle>
          <CardDescription>{tx("AI 按主题写口播，或直接用你自己的文案。")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Segmented
            ariaLabel={tx("文案来源")}
            options={[
              { value: "topic", label: tx("AI 创作") },
              { value: "script", label: tx("固定文案") },
              { value: "batch", label: tx("批量创作") },
            ]}
            value={mode}
            onChange={setMode}
          />
          {!hasLlm && (mode === "topic" || mode === "batch") && (
            <p className="text-sm text-warning">
              尚未配置 LLM。请到{" "}
              <Link className="underline" to="/settings/system">
                {tx('系统设置')}
              </Link>{" "}
              {tx('或「服务提供方」添加后再创作。')}
            </p>
          )}
          {mode === "batch" ? (
            <>
              <Field
                label={tx("主题列表")}
                hint={tx("一行一个主题，每个主题即该视频的标题，AI 分别生成口播文案并各出一条视频。上限 100 个。脚本 LLM 使用系统设置中的默认服务。")}
              >
                <textarea
                  className={`${areaClass} min-h-32`}
                  placeholder={tx("例如：\n三个提高效率的小技巧\n职场新人沟通指南\n五分钟学会番茄工作法")}
                  value={batchText}
                  onChange={(e) => setBatchText(e.target.value)}
                />
              </Field>
              <Field label={tx("分镜数")} hint={tx("每条视频的分镜数，范围 1 到 12，全部主题共用。")}>
                <NumberStepper ariaLabel={tx("分镜数")} min={1} max={12} value={count} onChange={setCount} />
              </Field>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {tx("共 {n} 个主题。每个主题一个任务、排队执行，可在任务中心查看或取消。", { n: batchTopics.length })}
              </p>
            </>
          ) : mode === "topic" ? (
            <>
              <PromptField
                label={tx("主题")}
                hint={tx("主题会作为标题显示在视频画面里；可先 ✨ 扩写意图，再由系统默认 LLM 写口播并拆分镜。")}
                value={topicValue}
                onChange={setTopicValue}
                jobScope="video-quick:topic-opt"
                task="quick_topic"
                aspect={aspect}
                workflow={tpl?.type === "video" ? videoPack?.name : imagePack?.name}
                placeholder={tx("例如：三个提高效率的小技巧，语气轻快，面向职场新人")}
              />
              <Field label={tx("分镜数")} hint={tx("范围 1 到 12。AI 按这个数量拆镜。")}>
                <NumberStepper ariaLabel={tx("分镜数")} min={1} max={12} value={count} onChange={setCount} />
              </Field>
              {(tpl?.type === "image" || tpl?.type === "video") && (
                <div className="flex flex-col gap-1.5">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={optimizeVisuals}
                      onChange={(e) => setOptimizeVisuals(e.target.checked)}
                    />
                    {tx('生成时用 LLM 写画面提示词')}
                  </label>
                  <span className="text-xs leading-relaxed text-muted-foreground">
                    {tx('开启后由 LLM 把口播改写成画面描述，再交给插图或视频工作流。是否再经 Guide 增强只由所选工作流包决定，与本开关无关。')}
                  </span>
                </div>
              )}
            </>
          ) : (
            <>
              <Field label={tx("主题")} hint={tx("作为标题显示在视频画面里，不经过 AI 改写。")}>
                <Input
                  placeholder={tx("例如：三个提高效率的小技巧")}
                  value={scriptTitle}
                  onChange={(e) => setScriptTitle(e.target.value)}
                />
              </Field>
              {tpl?.type === "image" || tpl?.type === "video" ? (
                <PromptField
                  label={tx("口播文案 / 画面提示词")}
                  hint={tx("原始输入为口播（按切分方式拆镜）；✨ 生成每镜画面提示词。开关决定合成时用画面词还是口播原文。")}
                  value={scriptVisual}
                  onChange={setScriptVisual}
                  jobScope="video-quick:script-opt"
                  task="quick_visual"
                  aspect={aspect}
                  workflow={tpl?.type === "video" ? videoPack?.name : imagePack?.name}
                  extraContext={
                    character
                      ? characterPromptContext(character.name, character.description, characterView)
                      : undefined
                  }
                  placeholder={tx("输入口播文案…")}
                  minRowsClass="min-h-28"
                />
              ) : (
                <Field label={tx("口播文案")} hint={tx("按下方切分方式拆成多个分镜，文案原样朗读。")}>
                  <textarea
                    className={`${areaClass} min-h-28`}
                    value={script}
                    onChange={(e) => {
                      setScriptVisual((prev) => ({ ...prev, raw: e.target.value }));
                    }}
                  />
                </Field>
              )}
              <Field label={tx("切分方式")} hint={tx("决定文案如何拆成一条条分镜。")}>
                <select className={selectClass} value={splitMode} onChange={(e) => setSplitMode(e.target.value)}>
                  <option value="paragraph">{tx("按段切分")}</option>
                  <option value="line">{tx("按行切分")}</option>
                  <option value="sentence">{tx("按句切分")}</option>
                </select>
              </Field>
            </>
          )}
          {mode !== "batch" && (
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={storyboardOnly} onChange={(e) => setStoryboardOnly(e.target.checked)} />
                {tx('生成分镜后暂停，人工确认后再合成')}
              </label>
              <span className="text-xs leading-relaxed text-muted-foreground">
                {tx('勾选后只出脚本和分镜 JSON，可以在下方修改画面提示词，确认无误再合成视频。')}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ② 分镜模板 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ImageIcon className="size-4" />{tx("分镜模板")}</CardTitle>
          <CardDescription>{tx("模板决定每镜的画面：静态样式纯排版、生成插图逐镜出图、生成视频逐镜出片段。")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label={tx("画幅")} hint={tx("竖屏适合短视频平台，横屏适合宽画面。")}>
            <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
              {ASPECTS.map((a) => (
                <option key={a.value} value={a.value}>{tx(a.label)}</option>
              ))}
            </select>
          </Field>
          {usableTemplates && usableTemplates.length === 0 && (
            <p className="text-sm text-muted-foreground">{tx("当前画幅没有模板，请到「模板管理」上传。")}</p>
          )}
          {/* 已选模板摘要：缩略图 + 名称 + 类型，默认折叠不占空间 */}
          {tpl && (
            <div className="flex items-center gap-3 rounded-xl border border-primary/50 bg-primary/5 p-2">
              <TemplateThumb aspect={aspect} name={tpl.name} className="h-24 w-auto shrink-0 rounded-lg" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{tpl.name}</div>
                <div className="text-xs leading-relaxed text-muted-foreground">
                  {tpl.type_label} · {tpl.width}x{tpl.height}
                  {tpl.source === "builtin" ? tx(" · 内置") : ""}
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => setPickerOpen((v) => !v)}>
                {pickerOpen ? tx("收起") : tx("更换模板")}
              </Button>
            </div>
          )}
          {/* 模板选择器：先选模式（画面来源），再选该模式下的模板 */}
          {(pickerOpen || !tpl) && (
            <div className="flex flex-col gap-3">
              <Segmented
                ariaLabel={tx("分镜模式")}
                options={TYPE_MODES.map((m) => ({ value: m.value, label: tx(m.label) }))}
                value={modeType}
                onChange={switchModeType}
              />
              <p className="text-xs text-muted-foreground">
                {tx(TYPE_MODES.find((m) => m.value === modeType)?.desc ?? "")}
              </p>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {usableTemplates
                  ?.filter((t) => t.type === modeType)
                  .map((t) => (
                    <button
                      key={t.name}
                      type="button"
                      onClick={() => {
                        setTemplateName(t.name);
                        setPickerOpen(false);
                      }}
                      className={cn(
                        "group flex flex-col overflow-hidden rounded-xl border border-border text-left transition-colors hover:border-primary/60",
                        tpl?.name === t.name && "border-primary ring-2 ring-primary/40",
                      )}
                    >
                      <TemplateThumb
                        aspect={aspect}
                        name={t.name}
                        className={cn("w-full", aspect === "16:9" ? "aspect-video" : aspect === "1:1" ? "aspect-square" : "aspect-[9/16]")}
                      />
                      <span className="truncate px-2 py-1.5 text-xs">{t.name}</span>
                    </button>
                  ))}
              </div>
              {usableTemplates && !usableTemplates.some((t) => t.type === modeType) && (
                <p className="text-sm text-muted-foreground">{tx("该模式下当前画幅没有模板，可到「模板管理」上传。")}</p>
              )}
            </div>
          )}
          {tpl?.type === "image" && tpl.needs_image && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("插图服务")} hint={tx("逐镜生成插图的图像 Provider。")}>
                  <select
                    className={selectClass}
                    value={imageProvider?.id ?? ""}
                    onChange={(e) => setImageProviderId(Number(e.target.value))}
                  >
                    {imageProviders?.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </Field>
                {imageProvider?.type === "comfyui" && (
                  <Field label={tx("插图工作流")} hint={tx("逐镜出图用的工作流包，其参数（模型等）在下方展开。")}>
                    <WorkflowPackControl name={imagePack?.name} description={imagePack?.description}>
                      <PackSelect
                        packs={imagePacks}
                        value={imagePack?.name ?? ""}
                        onChange={setImageWorkflow}
                        ariaLabel={tx("插图工作流")}
                      />
                    </WorkflowPackControl>
                  </Field>
                )}
                <Field label={tx("登场角色")} hint={tx("可选。外观描述会加到每个画面提示词前面，帮助各镜头保持同一个人。")}>
                  <select className={selectClass} value={characterId} onChange={(e) => setCharacterId(e.target.value ? Number(e.target.value) : "")}>
                    <option value="">{tx("不指定")}</option>
                    {characters?.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label={tx("风格前缀")} hint={tx("加在每个画面提示词前面，保持全片风格统一，可以留空。")}>
                  <Input value={stylePrefix} onChange={(e) => setStylePrefix(e.target.value)} placeholder={tx("例如：电影感，浅景深，")} />
                </Field>
              </div>
            </>
          )}
          {tpl?.type === "video" && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("视频服务")} hint={tx("逐镜生成片段的 Provider（决定下方模型列表来源）。")}>
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
                <Field
                  label={tx("视频工作流")}
                  hint={
                    character
                      ? tx("选了角色后可以改用图生视频包。每镜按入镜视角送一张角色图，用来锁住同一个人。")
                      : tx("每个分镜跑一遍该工作流。带 Guide 的包（如 *_enhancer）会在包内增强提示词；不带的包（如 *_uncensored）不会。与上方 LLM 开关无关。")
                  }
                >
                  <WorkflowPackControl name={videoPack?.name} description={videoPack?.description}>
                    <PackSelect
                      packs={videoPacks}
                      value={videoPack?.name ?? ""}
                      onChange={setVideoWorkflow}
                      ariaLabel={tx("视频工作流")}
                    />
                  </WorkflowPackControl>
                </Field>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("登场角色")} hint={tx("可选。外观会写进每镜画面，并在图生视频包里送入这一镜的角色图。")}>
                  <select className={selectClass} value={characterId} onChange={(e) => setCharacterId(e.target.value ? Number(e.target.value) : "")}>
                    <option value="">{tx("不指定")}</option>
                    {characters?.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label={tx("入镜视角")} hint={tx("单张参考图用这个视角。选了定妆照会整张送入每一镜；其余视角可以按镜轮换。")}>
                  <select className={selectClass} value={characterView} onChange={(e) => setCharacterView(e.target.value)} disabled={!character}>
                    {CHARACTER_VIEWS.map(([key, label]) => (
                      <option key={key} value={key}>{tx(label)}</option>
                    ))}
                  </select>
                </Field>
                <Field label={tx("风格前缀")} hint={tx("加在每个画面提示词前面，保持全片风格统一，可以留空。")}>
                  <Input value={stylePrefix} onChange={(e) => setStylePrefix(e.target.value)} placeholder={tx("例如：电影感，浅景深，")} />
                </Field>
              </div>
              <p className="text-xs leading-relaxed text-warning">
                {tx("注意：视频模式每个分镜都会跑一遍文生视频工作流，{count} 镜约等于 {count} 次本地/远程视频生成，整体耗时较长。", { count })}
              </p>
            </>
          )}
          {/* 文字与字幕：模板标题/文案的显隐与字号倍率，视频烧录字幕的开关与字号 */}
          <div className="flex flex-col gap-3 border-t border-border pt-3">
            <span className="text-sm font-medium text-foreground">{tx("文字与字幕")}</span>
            {tpl?.type !== "video" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("模板标题")} hint={tx("模板排版顶部的视频标题。关闭后不显示；倍率 1 为模板默认大小。")}>
                  <div className="flex items-center gap-2">
                    <label className="flex shrink-0 items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={showTitle}
                        onChange={(e) => setShowTitle(e.target.checked)}
                      />
                      {tx('显示')}
                    </label>
                    <div className="min-w-0 flex-1">
                      <NumberStepper ariaLabel={tx("标题字号倍率")} min={0.5} max={2} step={0.1} value={titleScale} onChange={setTitleScale} />
                    </div>
                  </div>
                </Field>
                <Field label={tx("模板文案")} hint={tx("模板排版里的分镜文案（卡片/正文区）。关闭后模板不显示文案；画面底部的字幕条由下方「视频字幕」单独控制。")}>
                  <div className="flex items-center gap-2">
                    <label className="flex shrink-0 items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={showText}
                        onChange={(e) => setShowText(e.target.checked)}
                      />
                      {tx('显示')}
                    </label>
                    <div className="min-w-0 flex-1">
                      <NumberStepper ariaLabel={tx("文案字号倍率")} min={0.5} max={2} step={0.1} value={textScale} onChange={setTextScale} />
                    </div>
                  </div>
                </Field>
              </div>
            )}
            <div className="flex flex-col gap-3">
              <Field label={tx("视频字幕")} hint={tx("烧录在画面底部的字幕条（分镜文案），由 ffmpeg 生成，与模板内文案相互独立。关闭后成片无字幕。")}>
                <label className="flex h-11 items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={showSubtitle}
                    onChange={(e) => setShowSubtitle(e.target.checked)}
                  />
                  {tx('烧录字幕')}
                </label>
              </Field>
              <Field label={tx("字幕字号")} hint={tx("底部字幕条的字号。0 为自动（跟随画面高度）；静态/插图/视频模式通用。")}>
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
          </div>
        </CardContent>
      </Card>

      {/* ③ 配音合成 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Volume2 className="size-4" />{tx("配音合成")}</CardTitle>
          <CardDescription>
            {tx('逐镜配音。ComfyUI 语音工作流、Liber Speech（音色库克隆）或本机/第三方 TTS（服务音色列表）。')}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {tpl?.type === "video" && (
            <Field label={tx("声音来源")} hint={tx("自定义配音按文案合成。模型原声保留文生视频自己生成的音轨。")}>
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
          <Field
            label={tx("配音服务")}
            hint={tx("已配置且具备 tts 能力的服务。「本地」为微软 Edge TTS。")}
          >
            <select
              className={selectClass}
              value={ttsProvider?.id ?? ""}
              onChange={(e) => setTtsProviderId(Number(e.target.value))}
            >
              {ttsProviders?.map((p) => (
                <option key={p.id} value={p.id}>
                  {ttsProviderLabel(p, tx)}
                </option>
              ))}
            </select>
          </Field>
          {ttsIsComfy ? (
            <>
              <Field label={tx("语音工作流")} hint={tx("选择已导入的 Comfy 语音工作流包，朗读文本会自动注入。")}>
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
                <p className="text-sm text-muted-foreground">
                  {tx('没有 tts 能力的工作流包，请到「设置 → 工作流包」导入（如 IndexTTS2）。')}
                </p>
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

      <AdvancedPanel summary={advancedSummary || tx("采样、配乐与权重")}>
        {tpl?.type === "image" && imagePack && hasAccel(imagePack.accel) && imagePack.accel && (
          <AccelControl
            accel={imagePack.accel}
            providerId={imageProvider?.id}
            value={imageAccel}
            onChange={setImageAccel}
            inputs={imagePack.inputs}
            onApplyPreset={(patch) => setImageExtra((prev) => ({ ...prev, ...patch }))}
          />
        )}
        {tpl?.type === "image" && imageProvider?.type === "comfyui" && imagePack && (
          <WorkflowInputs
            inputs={imagePack.inputs}
            values={imageExtra}
            onChange={(k, v) => setImageExtra((prev) => ({ ...prev, [k]: v }))}
            exclude={["prompt", "width", "height"]}
            providerId={imageProvider.id}
          />
        )}
        {tpl?.type === "video" && videoPack && hasAccel(videoPack.accel) && videoPack.accel && (
          <AccelControl
            accel={videoPack.accel}
            providerId={videoProvider?.id}
            value={videoAccel}
            onChange={setVideoAccel}
            inputs={videoPack.inputs}
            onApplyPreset={(patch) => setVideoExtra((prev) => ({ ...prev, ...patch }))}
          />
        )}
        {tpl?.type === "video" && videoPack && (
          <WorkflowInputs
            inputs={videoPack.inputs}
            values={videoExtra}
            onChange={(k, v) => setVideoExtra((prev) => ({ ...prev, [k]: v }))}
            exclude={["prompt", "width", "height", "image"]}
            providerId={videoProvider?.id}
            fps={videoPack.fps}
          />
        )}
        {!nativeAudio && ttsIsComfy && ttsPack && (
          <WorkflowInputs
            inputs={ttsPack.inputs}
            values={ttsExtra}
            onChange={(k, v) => setTtsExtra((prev) => ({ ...prev, [k]: v }))}
            exclude={["text"]}
            providerId={ttsProvider?.id}
          />
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={tx("背景音乐")} hint={tx("从音乐库选择；留空则只有人声。")}>
            <select
              className={selectClass}
              value={bgmName}
              onChange={(e) => setBgmName(e.target.value)}
            >
              <option value="">{tx("无背景音乐")}</option>
              {bgmName && !bgmList?.some((b) => b.name === bgmName) && (
                <option value={bgmName}>{bgmName}{tx("（已不在库中）")}</option>
              )}
              {bgmList?.map((b) => (
                <option key={b.name} value={b.name}>{b.name}</option>
              ))}
            </select>
          </Field>
          <Field label={tx("BGM 音量")} hint={tx("0 到 1，建议 0.1 到 0.3，别盖过人声。")}>
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
        <Field label={tx("上传新音乐")} hint={tx("上传到音乐库并直接选中；支持 MP3 / WAV / M4A / OGG，以后可直接复用。")}>
          <FileDrop
            accept="audio/*"
            title={uploadBgm.isPending ? tx("上传中…") : tx("点击或拖拽上传，自动存入音乐库")}
            subtitle="MP3 / WAV / M4A / OGG / FLAC / AAC"
            onSelect={(fs) => {
              const f = fs?.[0];
              if (f) uploadBgm.mutate(f);
            }}
          />
        </Field>
      </AdvancedPanel>
      </div>
        }
        footer={
          <div className="flex flex-col gap-2">
            {error && <p className="text-sm text-danger">{error}</p>}
            {running && job?.steps?.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {formatStepName(String(job.steps[job.steps.length - 1]?.name ?? ""), tx)}
              </p>
            )}
            {mode === "batch" ? (
              <Button className={submitButtonClass} onClick={() => batchSubmit.mutate()} disabled={batchDisabled}>
                {batchSubmit.isPending ? tx("提交中…") : tx("批量生成 {n} 个视频", { n: batchTopics.length })}
              </Button>
            ) : (
              <Button className={submitButtonClass} onClick={() => submit.mutate()} disabled={submitDisabled}>
                {running ? tx("进行中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始创作")}
              </Button>
            )}
          </div>
        }
        right={
          <div className="flex flex-col gap-6">
            {batchJobs && <BatchStatus jobs={batchJobs} />}
            {storyboardText && (
              <Card>
                <CardHeader>
                  <CardTitle>{tx("分镜编辑")}</CardTitle>
                  <CardDescription>{tx("修改 frames 后重新合成（跳过 LLM）。")}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <Field label={tx("分镜 JSON")} hint={tx("每镜一条：text 是口播句、visual 是画面提示词。")}>
                    <textarea
                      className={`${areaClass} min-h-48 font-mono text-xs`}
                      value={storyboardText}
                      onChange={(e) => setStoryboardText(e.target.value)}
                    />
                  </Field>
                  <Button className="w-fit" variant="outline" onClick={() => resubmit.mutate()} disabled={resubmit.isPending || !!running}>
                    {tx('按修改后的分镜重新合成')}
                  </Button>
                </CardContent>
              </Card>
            )}
            <ResultPanel
              job={job ?? null}
              mediaKind="video"
              historyKind="video"
              jobKind="video.quick"
              emptyHint={tx("一句话或一段文案，生成一条短视频")}
              meta={[
                { label: tx("画幅"), value: aspect },
                { label: tx("模板"), value: tpl ? tx("{name}（{type}）", { name: tpl.name, type: tx(tpl.type_label) }) : "" },
                { label: tx("内容"), value: mode === "batch" ? tx("批量 {n} 个主题", { n: batchTopics.length }) : mode === "topic" ? effectiveTopic : script },
              ]}
            />
          </div>
        }
      />
    </div>
  );
}

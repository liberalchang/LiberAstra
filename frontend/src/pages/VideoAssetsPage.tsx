import { Images, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
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
  type PromptFieldValue,
} from "@/components/PromptField";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { SplitPane } from "@/components/ui/split-pane";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { formatStepName } from "@/lib/utils";
import { Film, X } from "lucide-react";

const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp)$/i;

/** 自定义素材：图片/视频素材 + 文案/主题 → 配音字幕短片。支持素材动画（i2v）与背景音乐。 */
export function VideoAssetsPage() {
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

  // ---- ② 素材分析（可选：视觉模型逐素材产出内容描述，喂给写文案的 LLM）----
  const { data: analysisPacks } = useQuery({
    queryKey: ["workflows", "analysis"],
    queryFn: () => api.listWorkflows("analysis"),
  });
  const comfyProviders = enabled?.filter((p) => p.type === "comfyui");
  const [analysisEnabled, setAnalysisEnabled] = usePersistentState("video-assets:analysis-enabled", false);
  const [analysisProviderId, setAnalysisProviderId] = usePersistentState<number | "">("video-assets:analysis-provider", "");
  const analysisProvider = comfyProviders?.find((p) => p.id === analysisProviderId) ?? comfyProviders?.[0];
  const [analysisImageWorkflow, setAnalysisImageWorkflow] = usePersistentState("video-assets:analysis-image-workflow", "");
  const [analysisVideoWorkflow, setAnalysisVideoWorkflow] = usePersistentState("video-assets:analysis-video-workflow", "");
  const analysisImagePack = analysisPacks?.find((p) => p.name === analysisImageWorkflow) ?? analysisPacks?.[0];
  const analysisVideoPack = analysisPacks?.find((p) => p.name === analysisVideoWorkflow) ?? analysisPacks?.[0];
  const [analysisExtra, setAnalysisExtra] = usePersistentState<Record<string, string>>("video-assets:analysis-extra", {});

  // ---- ③ 文案与标题 ----
  const [mode, setMode] = usePersistentState<"script" | "topic">("video-assets:mode", "script");
  const [script, setScript] = usePersistentState("video-assets:script", "");
  const [legacyTopic, setLegacyTopic] = usePersistentState("video-assets:topic", "");
  const [topicValue, setTopicValue] = useState<PromptFieldValue>(() => emptyPromptValue(legacyTopic));
  const effectiveTopic = resolveEffectivePrompt(topicValue);
  const [title, setTitle] = usePersistentState("video-assets:title", "");
  const [duration, setDuration] = usePersistentState("video-assets:duration", 30);
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  // ---- ③ 素材动画（静态图片 → i2v 动起来）----
  const [animate, setAnimate] = usePersistentState("video-assets:animate", false);
  const [animatePrompt, setAnimatePrompt] = useState<PromptFieldValue>(() => emptyPromptValue(""));
  const [videoProviderId, setVideoProviderId] = usePersistentState<number | "">("video-assets:video-provider", "");
  const videoProvider = videoProviders?.find((p) => p.id === videoProviderId) ?? videoProviders?.[0];
  const { data: i2vPacks } = useQuery({
    queryKey: ["workflows", "i2v"],
    queryFn: () => api.listWorkflows("i2v"),
    enabled: animate,
  });
  const [videoWorkflow, setVideoWorkflow] = usePersistentState("video-assets:video-workflow", "");
  const videoPack = i2vPacks?.find((p) => p.name === videoWorkflow) ?? i2vPacks?.[0];
  const [videoExtra, setVideoExtra] = usePersistentState<Record<string, string>>("video-assets:video-extra", {});
  const [videoAccel, setVideoAccel] = usePersistentState<AccelState>(
    `video-assets:accel:${videoPack?.name ?? "none"}`,
    defaultAccelState(videoPack?.accel),
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
  /** 克隆服务（Liber Speech）用音色库；其余服务（edge_tts / 第三方 TTS）用服务自己的音色列表 */
  const isLibraryVoice = ttsProvider?.type === "liber_speech" || ttsProvider == null;
  const serviceVoices = isLibraryVoice ? [] : (ttsProvider?.models ?? []);
  // 切到非克隆服务且还没拉过音色列表时自动拉一次
  useEffect(() => {
    if (ttsProvider && !isLibraryVoice && ttsProvider.models.length === 0 && !refreshModels.isPending) {
      refreshModels.mutate(ttsProvider.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ttsProvider?.id, isLibraryVoice]);

  // ---- ⑤ 画幅与背景音乐 ----
  const [aspect, setAspect] = usePersistentState("video-assets:aspect", "9:16");
  const [bgmName, setBgmName] = usePersistentState("video-assets:bgm-name", "");
  const [bgmVolume, setBgmVolume] = usePersistentState("video-assets:bgm-volume", "0.2");

  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("video-assets");

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append("images", f);
      if (mode === "script") form.set("script", script);
      else form.set("topic", effectiveTopic);
      if (title) form.set("title", title);
      form.set("duration", String(duration));
      form.set("aspect", aspect);
      if (!ttsIsComfy) {
        if (isLibraryVoice && voiceRecordId !== "") form.set("voice_record_id", String(voiceRecordId));
        else form.set("voice", voiceName);
      }
      if (ttsProvider) form.set("tts_provider_id", String(ttsProvider.id));
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
      if (analysisEnabled && (analysisImagePack || analysisVideoPack)) {
        if (analysisProvider) form.set("analysis_provider_id", String(analysisProvider.id));
        if (analysisImagePack) form.set("analysis_image_workflow", analysisImagePack.name);
        if (analysisVideoPack) form.set("analysis_video_workflow", analysisVideoPack.name);
        form.set("analysis_inputs", JSON.stringify(Object.fromEntries(Object.entries(analysisExtra).filter(([, v]) => v !== ""))));
      }
      if (bgmName) {
        form.set("bgm_path", `bgm/${bgmName}`);
        form.set("bgm_volume", bgmVolume || "0.2");
      }
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
    files.length > 0 &&
    (mode === "script" ? script : effectiveTopic) &&
    (mode !== "topic" || hasLlm) &&
    (ttsIsComfy ? !!ttsPack : isLibraryVoice ? voiceRecordId !== "" || !!voiceName : !!voiceName) &&
    (!animate || !hasImage || !!videoPack);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="clips" icon={Images} title="自定义素材" description="上传图片或视频素材，配旁白和字幕后拼成短片，支持标题卡、素材动画与背景音乐。" />
      <SplitPane
        storageKey="video-assets"
        left={
      <div className="flex flex-col gap-4">
      {/* ① 素材 */}
      <Card>
        <CardHeader>
          <CardTitle>素材</CardTitle>
          <CardDescription>图片和视频都可以，顺序即分镜顺序。视频素材会循环/截断对齐配音时长。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Field label="素材文件" hint="支持 JPG/PNG/WebP/GIF 图片和 MP4/MOV/AVI/WebM 视频，可分多次添加。">
            <FileDrop
              accept="image/*,video/*"
              multiple
              clearAfterSelect
              title="点击或拖拽上传素材"
              subtitle="图片与视频，支持多选、多次添加"
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
                    title={`移除 ${f.name}`}
                    className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-red-500 group-hover:opacity-100"
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

      {/* ② 素材分析（可选） */}
      <Card>
        <CardHeader>
          <CardTitle>素材分析</CardTitle>
          <CardDescription>
            开启后先用视觉模型逐素材生成内容描述，写文案的 AI 会参考真实内容而不是只看文件名。需要
            ComfyUI 装 ComfyUI-AILab 插件与 Qwen-VL 视觉模型。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={analysisEnabled}
              onChange={(e) => setAnalysisEnabled(e.target.checked)}
            />
            启用素材分析（较慢，每个素材一次视觉推理）
          </label>
          {analysisEnabled && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="分析服务" hint="执行分析工作流的 ComfyUI。">
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
                <Field label="图片分析工作流" hint="analysis 能力包，如 analysis_image_qwenvl。">
                  <select
                    className={selectClass}
                    value={analysisImagePack?.name ?? ""}
                    onChange={(e) => setAnalysisImageWorkflow(e.target.value)}
                  >
                    {analysisPacks?.map((p) => (
                      <option key={p.name} value={p.name}>{p.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="视频分析工作流" hint="有视频素材时使用，如 analysis_video_qwenvl。">
                  <select
                    className={selectClass}
                    value={analysisVideoPack?.name ?? ""}
                    onChange={(e) => setAnalysisVideoWorkflow(e.target.value)}
                  >
                    {analysisPacks?.map((p) => (
                      <option key={p.name} value={p.name}>{p.name}</option>
                    ))}
                  </select>
                </Field>
              </div>
              {analysisPacks && analysisPacks.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  没有 analysis 能力的工作流包，请到「设置 → 工作流包」导入。
                </p>
              )}
              {analysisImagePack && (
                <WorkflowInputs
                  inputs={analysisImagePack.inputs}
                  values={analysisExtra}
                  onChange={(k, v) => setAnalysisExtra((prev) => ({ ...prev, [k]: v }))}
                  exclude={["image", "video"]}
                  providerId={analysisProvider?.id}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* ③ 文案与标题 */}
      <Card>
        <CardHeader>
          <CardTitle>文案与标题</CardTitle>
          <CardDescription>标题会作为 2 秒标题卡放在片头；文案决定每镜的口播与字幕。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="视频标题" hint="选填。留空则没有标题卡。">
            <Input placeholder="例如：宠物店年终大促" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Segmented
            ariaLabel="文案来源"
            options={[
              { value: "script", label: "自备文案（按行对应素材）" },
              { value: "topic", label: "主题生成文案" },
            ]}
            value={mode}
            onChange={setMode}
          />
          {mode === "script" ? (
            <Field label="口播文案" hint="每行一句，行数建议与素材数量一致；不够会循环使用。">
              <textarea
                className={`${areaClass} min-h-24`}
                value={script}
                onChange={(e) => setScript(e.target.value)}
              />
            </Field>
          ) : (
            <>
              {!hasLlm && (
                <p className="text-sm text-amber-700 dark:text-amber-400">
                  尚未配置 LLM。请到{" "}
                  <Link className="underline" to="/settings/system">
                    系统设置
                  </Link>{" "}
                  或「服务提供方」添加。
                </p>
              )}
              <PromptField
                label="主题"
                hint="AI 结合素材按目标时长写口播；脚本 LLM 使用系统设置中的默认服务。"
                value={topicValue}
                onChange={(v) => {
                  setTopicValue(v);
                  setLegacyTopic(v.raw);
                }}
                task="assets_topic"
                aspect={aspect}
                placeholder="例如：宠物店年终大促，语气热情"
              />
              <Field label="目标时长（秒）" hint="AI 按它控制文案长度，5 到 600。">
                <NumberStepper ariaLabel="目标时长" min={5} max={600} step={5} value={duration} onChange={setDuration} />
              </Field>
            </>
          )}
        </CardContent>
      </Card>

      {/* ③ 素材动画（常驻显示；没有图片素材时提示） */}
      <Card>
        <CardHeader>
          <CardTitle>素材动画</CardTitle>
          <CardDescription>
            开启后，静态图片先经 i2v 工作流动画化再合成（每张图一次图生视频，较慢）。视频素材不受影响。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!hasImage && (
            <p className="text-sm text-muted-foreground">当前没有图片素材。上传图片后可启用素材动画。</p>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={animate}
              disabled={!hasImage}
              onChange={(e) => setAnimate(e.target.checked)}
            />
            静态图片动画化（i2v）
          </label>
            {animate && (
              <>
                <PromptField
                  label="动画提示词"
                  hint="可选。描述图片如何动起来；留空则用默认轻微推镜运动。"
                  value={animatePrompt}
                  onChange={setAnimatePrompt}
                  task="i2v"
                  workflow={videoPack?.name}
                  aspect={aspect}
                  placeholder="例如：微风吹动，缓慢推近，环境轻柔"
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="动画服务" hint="执行 i2v 的视频 Provider。">
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
                  <Field label="动画工作流" hint="i2v 能力的工作流包，图片作为首帧。">
                    <select
                      className={selectClass}
                      value={videoPack?.name ?? ""}
                      onChange={(e) => setVideoWorkflow(e.target.value)}
                    >
                      {i2vPacks?.map((p) => (
                        <option key={p.name} value={p.name}>{p.name}</option>
                      ))}
                    </select>
                  </Field>
                </div>
                {videoPack && hasAccel(videoPack.accel) && videoPack.accel && (
                  <AccelControl
                    accel={videoPack.accel}
                    providerId={videoProvider?.id}
                    value={videoAccel}
                    onChange={setVideoAccel}
                    onApplyPreset={(preset) =>
                      setVideoExtra((prev) => {
                        const next = { ...prev };
                        for (const [k, v] of Object.entries(preset)) {
                          if (next[k] == null || next[k] === "") next[k] = v;
                        }
                        return next;
                      })
                    }
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
          <CardTitle>配音</CardTitle>
          <CardDescription>逐素材配音：ComfyUI 语音工作流、Liber Speech 或第三方 TTS API。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="配音服务" hint="只列出已启用、且具备 tts 能力的 Provider。">
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
              <Field label="语音工作流" hint="tts 能力的工作流包，口播文本会自动注入。">
                <select
                  className={selectClass}
                  value={ttsPack?.name ?? ""}
                  onChange={(e) => setTtsWorkflow(e.target.value)}
                >
                  {ttsPacks?.map((p) => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </Field>
              {ttsPacks && ttsPacks.length === 0 && (
                <p className="text-sm text-muted-foreground">没有 tts 能力的工作流包，请到「设置 → 工作流包」导入。</p>
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
              <Field label="音色" hint="选自音色库（参考音频克隆）。不选则填写音色名。">
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
              {voiceRecordId === "" && (
                <Field label="音色名" hint="Liber Speech 用语言代码，例如 zh、en。">
                  <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
                </Field>
              )}
            </div>
          ) : (
            <Field label="音色" hint="来自所选服务的音色列表；点右侧按钮从服务拉取，也可直接输入。">
              <div className="flex gap-2">
                {serviceVoices.length > 0 ? (
                  <select
                    className={selectClass}
                    value={voiceName}
                    onChange={(e) => setVoiceName(e.target.value)}
                  >
                    <option value="">选择音色…</option>
                    {voiceName && !serviceVoices.includes(voiceName) && (
                      <option value={voiceName}>{voiceName}（不在列表中）</option>
                    )}
                    {serviceVoices.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                ) : (
                  <Input
                    placeholder={refreshModels.isPending ? "正在从服务拉取音色…" : "拉取失败时可手动输入，如 zh-CN-XiaoxiaoNeural"}
                    value={voiceName}
                    onChange={(e) => setVoiceName(e.target.value)}
                  />
                )}
                <Button
                  variant="outline"
                  size="icon"
                  title="从服务拉取音色列表"
                  disabled={!ttsProvider || refreshModels.isPending}
                  onClick={() => ttsProvider && refreshModels.mutate(ttsProvider.id)}
                >
                  <RefreshCw />
                </Button>
              </div>
            </Field>
          )}
        </CardContent>
      </Card>

      {/* ⑥ 画幅与背景音乐 */}
      <Card>
        <CardHeader>
          <CardTitle>画幅与背景音乐</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="画幅" hint="成片宽高比。">
              <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
                <option value="9:16">9:16 竖屏</option>
                <option value="1:1">1:1 方形</option>
                <option value="16:9">16:9 横屏</option>
              </select>
            </Field>
            <Field label="背景音乐" hint="从音乐库选择；留空则只有人声。">
              <select className={selectClass} value={bgmName} onChange={(e) => setBgmName(e.target.value)}>
                <option value="">无背景音乐</option>
                {bgmList?.map((b) => (
                  <option key={b.name} value={b.name}>{b.name}</option>
                ))}
              </select>
            </Field>
            <Field label="BGM 音量" hint="0 到 1，建议 0.1 到 0.3。">
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
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!ready || submit.isPending || !!running}>
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
            </Button>
            {running && job?.steps?.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {formatStepName(String(job.steps[job.steps.length - 1]?.name ?? ""))}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
      </div>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="video"
            historyKind="video"
            emptyHint="上传素材，拼成一条短片"
            meta={[
              { label: "画幅", value: aspect },
              { label: "标题", value: title },
              { label: "内容", value: mode === "script" ? script : effectiveTopic },
            ]}
          />
        }
      />
    </div>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { AudioLines } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { AssetPickButton } from "@/components/AssetPickButton";
import { GenerateButton } from "@/components/GenerateButton";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { SPEECH_LANGUAGES } from "@/components/SpeechLanguageSelect";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";
import { assetAsFile } from "@/lib/assets";

const VIDEO_EXT = /\.(mp4|mov|mkv|webm|avi|m4v)$/i;

function isVideoFile(file: File | null): boolean {
  return Boolean(file && (file.type.startsWith("video/") || VIDEO_EXT.test(file.name)));
}

export function VcPage() {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });

  const vcProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("vc"));
  const [providerId, setProviderId] = usePersistentState<number | "">("vc:provider", "");
  const provider = vcProviders?.find((p) => p.id === providerId) ?? vcProviders?.[0];
  const { data: speechCatalog, error: catalogError } = useQuery({
    queryKey: ["speech-catalog"],
    queryFn: api.getSpeechCatalog,
    enabled: Boolean(provider),
    retry: false,
  });

  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("vc:voice-record", "");
  const [model, setModel] = usePersistentState("vc:model", "");
  const [format, setFormat] = usePersistentState("vc:format", "mp3");
  const [language, setLanguage] = usePersistentState("vc:language", "");
  const [separateBgm, setSeparateBgm] = usePersistentState("vc:separate-bgm", false);
  const [burnSubtitles, setBurnSubtitles] = usePersistentState("vc:burn-subtitles", false);
  const [subtitleSize, setSubtitleSize] = usePersistentState("vc:subtitle-size", 0);
  const [subtitleColor, setSubtitleColor] = usePersistentState("vc:subtitle-color", "#FFFFFF");
  const [file, setFile] = useState<File | null>(null);
  const [subtitleFile, setSubtitleFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("vc");

  const libraryVoices = (voices ?? []).filter((voice) => voice.ref_audio_path);
  const selectedVoice = libraryVoices.find((voice) => voice.id === voiceRecordId);
  const vcModels = speechCatalog?.vc_models ?? [];
  const noVcModels = speechCatalog !== undefined && vcModels.length === 0;
  const isVideo = isVideoFile(file);
  const defaultModel = prefs?.default_vc_model || "";
  const running = job && (job.status === "pending" || job.status === "running");

  const submit = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error(tx("请先选择音频或视频"));
      if (voiceRecordId === "") throw new Error(tx("请选择音色"));
      const form = new FormData();
      form.set("file", file);
      form.set("voice_record_id", String(voiceRecordId));
      if (provider) form.set("provider_id", String(provider.id));
      if (model) form.set("model", model);
      form.set("format", format === "wav" ? "wav" : "mp3");
      form.set("separate_bgm", separateBgm ? "true" : "false");
      if (language) form.set("language", language);
      if (isVideo) {
        form.set("burn_subtitles", burnSubtitles ? "true" : "false");
        form.set("subtitle_size", String(subtitleSize || 0));
        form.set("subtitle_color", subtitleColor);
      }
      if (subtitleFile) form.set("subtitle", subtitleFile);
      return api.submitVc(form);
    },
    onSuccess: (submitted) => {
      setError(null);
      setJobId(submitted.id);
    },
    onError: (err) => setError(err.message),
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="vc"
        icon={AudioLines}
        title={tx("换音")}
        description={tx("保持时间轴不变，把音频或视频里的人声替换成音色库中的目标音色。")}
      />
      <SplitPane
        storageKey="vc"
        left={
          <Card>
            <CardContent className="flex flex-col gap-4 pt-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("语音服务")} hint={tx("只列出已启用且具备 vc 能力的服务。")}>
                  <select
                    className={selectClass}
                    value={provider?.id ?? ""}
                    onChange={(e) => setProviderId(Number(e.target.value))}
                  >
                    {vcProviders?.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                    {(vcProviders?.length ?? 0) === 0 && (
                      <option value="">{tx("没有可用服务")}</option>
                    )}
                  </select>
                </Field>
                <Field label={tx("换音模型")} hint={tx("不选则使用系统设置里的换音模型。")}>
                  <select
                    className={selectClass}
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    <option value="">
                      {defaultModel ? `${tx("系统设置")} (${defaultModel})` : tx("系统设置")}
                    </option>
                    {vcModels.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  {noVcModels && (
                    <p className="text-xs text-muted-foreground">
                      {tx("语音服务未提供换音模型，请升级语音服务。")}
                    </p>
                  )}
                </Field>
                <Field label={tx("音色")} hint={tx("只列出有参考音频的音色记录。")}>
                  <select
                    className={selectClass}
                    value={voiceRecordId}
                    onChange={(e) =>
                      setVoiceRecordId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">{tx("选择音色…")}</option>
                    {libraryVoices.map((voice) => (
                      <option key={voice.id} value={voice.id}>
                        {voice.name}
                      </option>
                    ))}
                  </select>
                  {libraryVoices.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      {tx("音色库还没有带参考音频的音色。")}
                    </p>
                  )}
                </Field>
                <Field label={tx("音频格式")} hint={tx("mp3 体积小；wav 无损。")}>
                  <select
                    className={selectClass}
                    value={format === "wav" ? "wav" : "mp3"}
                    onChange={(e) => setFormat(e.target.value)}
                  >
                    <option value="mp3">mp3</option>
                    <option value="wav">wav</option>
                  </select>
                </Field>
                <Field label={tx("语言")} hint={tx("识别用；上传 srt 时忽略。")}>
                  <select
                    className={selectClass}
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    <option value="">{tx("自动")}</option>
                    {SPEECH_LANGUAGES.map((item) => (
                      <option key={item.code} value={item.code}>
                        {tx(item.label)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={tx("分离背景音")}
                  hint={tx("先拆人声和伴奏，只换人声再混回伴奏。")}
                >
                  <select
                    className={selectClass}
                    value={separateBgm ? "1" : "0"}
                    disabled={speechCatalog?.separate_available === false}
                    onChange={(e) => setSeparateBgm(e.target.value === "1")}
                  >
                    <option value="0">{tx("关闭")}</option>
                    <option value="1">{tx("开启")}</option>
                  </select>
                  {speechCatalog?.separate_available === false && (
                    <p className="text-xs text-muted-foreground">
                      {tx("语音服务未提供 Demucs 背景音分离。")}
                    </p>
                  )}
                </Field>
              </div>

              <Field
                label={tx("换音素材")}
                hint={tx("支持音频或视频，最大 200MB / 30 分钟。未覆盖的字幕区间保留原声。")}
              >
                <FileDrop
                  accept="audio/*,video/*"
                  title={tx("点击或拖拽上传音频或视频")}
                  subtitle={tx("支持音频和视频文件")}
                  names={file ? [file.name] : []}
                  onSelect={(files) => setFile(files?.[0] ?? null)}
                />
                <AssetPickButton
                  kind={["audio", "video"]}
                  onPick={async (assets) => {
                    if (assets[0]) setFile(await assetAsFile(assets[0]));
                  }}
                />
              </Field>

              <Field
                label={tx("字幕 srt（可选）")}
                hint={tx("不上传则自动识别；上传后跳过识别。")}
              >
                <FileDrop
                  accept=".srt,text/plain"
                  title={tx("点击或拖拽上传 srt")}
                  subtitle={tx("可选；未上传时自动识别字幕")}
                  names={subtitleFile ? [subtitleFile.name] : []}
                  onSelect={(files) => setSubtitleFile(files?.[0] ?? null)}
                />
                {subtitleFile && (
                  <Button variant="ghost" size="sm" onClick={() => setSubtitleFile(null)}>
                    {tx("清除")}
                  </Button>
                )}
              </Field>

              {isVideo && (
                <Field label={tx("烧录字幕")} hint={tx("只对视频输入生效。")}>
                  <select
                    className={selectClass}
                    value={burnSubtitles ? "1" : "0"}
                    onChange={(e) => setBurnSubtitles(e.target.value === "1")}
                  >
                    <option value="0">{tx("关闭")}</option>
                    <option value="1">{tx("开启")}</option>
                  </select>
                </Field>
              )}
              {isVideo && burnSubtitles && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label={tx("字号")} hint={tx("0 = 按视频高度自动")}>
                    <Input
                      type="number"
                      min={0}
                      max={200}
                      value={subtitleSize}
                      onChange={(e) => setSubtitleSize(Number(e.target.value) || 0)}
                    />
                  </Field>
                  <Field label={tx("颜色")}>
                    <Input
                      type="color"
                      value={subtitleColor}
                      onChange={(e) => setSubtitleColor(e.target.value)}
                    />
                  </Field>
                </div>
              )}

              {catalogError && (
                <p className="text-sm text-danger">
                  {catalogError instanceof Error
                    ? catalogError.message
                    : tx("读取语音服务模型失败")}
                </p>
              )}
              {error && <p className="text-sm text-danger">{error}</p>}
              <GenerateButton
                className={submitButtonClass}
                running={!!running}
                jobId={job?.id}
                progress={job?.progress}
                disabled={
                  !provider ||
                  !file ||
                  voiceRecordId === "" ||
                  !selectedVoice ||
                  noVcModels ||
                  submit.isPending
                }
                onGenerate={() => submit.mutate()}
                label={tx("开始换音")}
              />
            </CardContent>
          </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind={isVideo ? "video" : "audio"}
            historyKind={isVideo ? "video" : "audio"}
            emptyHint={tx("上传音频或视频，换音后得到新音视频和字幕")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              { label: tx("模型"), value: model || defaultModel || tx("系统设置") },
              { label: tx("音色"), value: selectedVoice?.name ?? "" },
              { label: tx("语言"), value: language || tx("自动") },
              { label: tx("格式"), value: format },
              { label: tx("文件"), value: file?.name ?? "" },
            ]}
          />
        }
      />
    </div>
  );
}

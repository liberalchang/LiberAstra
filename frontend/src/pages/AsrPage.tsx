import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { SPEECH_ASR_MODELS, asrModelHint } from "@/components/SpeechLanguageSelect";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";

/** 输出类型：空串 = 自动（后端按 txt → json → srt → vtt 优先级取第一个可用格式）。 */
const FORMAT_OPTIONS = [
  { value: "", label: "自动" },
  { value: "txt", label: "txt 纯文本" },
  { value: "json", label: "json 结构化" },
  { value: "srt", label: "srt 字幕" },
  { value: "vtt", label: "vtt 字幕" },
];

const CUSTOM_LANG = "__custom";

const LANGUAGE_OPTIONS = [
  { value: "", label: "自动检测" },
  { value: "zh", label: "中文 zh" },
  { value: "en", label: "英语 en" },
  { value: "ja", label: "日语 ja" },
  { value: "ko", label: "韩语 ko" },
  { value: "yue", label: "粤语 yue" },
  { value: "fr", label: "法语 fr" },
  { value: "de", label: "德语 de" },
  { value: "es", label: "西班牙语 es" },
  { value: "ru", label: "俄语 ru" },
  { value: CUSTOM_LANG, label: "自定义…" },
];

export function AsrPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const asrProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("asr"));

  const [providerId, setProviderId] = usePersistentState<number | "">("asr:provider", "");
  const provider = asrProviders?.find((p) => p.id === providerId) ?? asrProviders?.[0];
  const isSpeech = provider?.type === "liber_speech";
  const isOpenAi = provider?.type === "openai_stt";
  const [language, setLanguage] = usePersistentState("asr:language", "");
  const [customLanguage, setCustomLanguage] = usePersistentState("asr:language-custom", "");
  const [format, setFormat] = usePersistentState("asr:format", "");
  const [asrModel, setAsrModel] = usePersistentState("asr:model", "");
  const effectiveLanguage = language === CUSTOM_LANG ? customLanguage.trim() : language;
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("asr");
  const { data: speechCatalog } = useQuery({
    queryKey: ["speech-catalog"],
    queryFn: api.getSpeechCatalog,
    enabled: isSpeech,
    retry: false,
  });
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  const liberModels = speechCatalog?.asr_models?.length
    ? speechCatalog.asr_models
    : SPEECH_ASR_MODELS.filter((item) => item.id);
  const openAiModels = isOpenAi ? (provider?.models ?? []) : [];
  const prevType = useRef<string | undefined>(undefined);

  // 换识别服务后，上一服务的模型名不能带到下一个
  useEffect(() => {
    if (!provider?.type) return;
    if (prevType.current && prevType.current !== provider.type) setAsrModel("");
    prevType.current = provider.type;
  }, [provider?.type, setAsrModel]);

  useEffect(() => {
    if (!isOpenAi || !provider || provider.models.length > 0 || refreshModels.isPending) return;
    refreshModels.mutate(provider.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider?.id, isOpenAi, provider?.models.length]);

  const openAiModelKey = openAiModels.join("|");
  // 列表回来后，丢掉不属于这个服务、且是 Liber Speech 内置 id 的旧模型
  useEffect(() => {
    if (!isOpenAi || !openAiModelKey) return;
    const names = openAiModelKey.split("|");
    const builtIn = SPEECH_ASR_MODELS.some((item) => item.id && item.id === asrModel);
    if (builtIn && !names.includes(asrModel)) setAsrModel("");
  }, [asrModel, isOpenAi, openAiModelKey, setAsrModel]);

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("file", file!);
      if (provider) form.set("provider_id", String(provider.id));
      if (effectiveLanguage) form.set("language", effectiveLanguage);
      if (format) form.set("formats", format);
      // 只有 Liber Speech 才回退系统设置。OpenAI 兼容留空则用该服务自己的默认模型。
      const chosenModel = isSpeech ? (asrModel || prefs?.default_asr_model || "") : asrModel;
      if (chosenModel) form.set("model", chosenModel);
      return api.submitAsr(form);
    },
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");
  const modelLabel = isSpeech
    ? (asrModel || prefs?.default_asr_model || tx("系统设置"))
    : (asrModel || "whisper-1");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="asr" icon={Mic} title={tx("语音转文字")} description={tx("上传音频，导出文本和字幕。")} />
      <SplitPane
        storageKey="asr"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={tx("识别服务")} hint={tx("只列出已启用、且具备 asr 能力的 Provider。本机不内置识别模型。")}>
              <select
                className={selectClass}
                value={provider?.id ?? ""}
                onChange={(e) => setProviderId(Number(e.target.value))}
              >
                {asrProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={tx("识别模型")}
              hint={
                isSpeech
                  ? tx(asrModelHint(asrModel || prefs?.default_asr_model || ""))
                  : tx("不选则使用该服务的默认模型 whisper-1。")
              }
            >
              {isOpenAi ? (
                <div className="flex gap-2">
                  {openAiModels.length > 0 ? (
                    <select className={selectClass} value={asrModel} onChange={(e) => setAsrModel(e.target.value)}>
                      <option value="">{tx("默认 (whisper-1)")}</option>
                      {openAiModels.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder={refreshModels.isPending ? tx("正在从服务拉取模型…") : "whisper-1"}
                      value={asrModel}
                      onChange={(e) => setAsrModel(e.target.value)}
                    />
                  )}
                  <Button
                    variant="outline"
                    size="icon"
                    title={tx("从服务拉取模型列表")}
                    disabled={!provider || refreshModels.isPending}
                    onClick={() => provider && refreshModels.mutate(provider.id)}
                  >
                    <RefreshCw />
                  </Button>
                </div>
              ) : (
                <select className={selectClass} value={asrModel} onChange={(e) => setAsrModel(e.target.value)}>
                  <option value="">{tx("使用系统默认")}</option>
                  {liberModels.map((item) => (
                    <option key={item.id} value={item.id}>
                      {tx(item.label)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={tx("语言")} hint={tx("自动检测或选常用语言；其他语种选自定义后手动填写代码。")}>
              <select className={selectClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
                {LANGUAGE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {tx(o.label)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={tx("输出类型")} hint={tx("自动按 txt → json → srt → vtt 优先级输出单个文件。")}>
              <select className={selectClass} value={format} onChange={(e) => setFormat(e.target.value)}>
                {FORMAT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {tx(o.label)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {language === CUSTOM_LANG && (
            <Field label={tx("自定义语言代码")} hint={tx("例如 zh、en、pt，需识别服务支持。")}>
              <Input
                placeholder={tx("如 pt、it")}
                value={customLanguage}
                onChange={(e) => setCustomLanguage(e.target.value)}
              />
            </Field>
          )}
          <Field label={tx("音频文件")} hint={tx("支持音频或视频，可直接拖拽。完成后给出文本，并按输出类型导出文件。")}>
            <FileDrop
              accept="audio/*,video/*"
              title={tx("点击或拖拽上传音频")}
              subtitle={tx("支持音频和视频文件")}
              names={file ? [file.name] : []}
              onSelect={(fs) => setFile(fs?.[0] ?? null)}
            />
          </Field>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button className={submitButtonClass} onClick={() => submit.mutate()} disabled={!file || submit.isPending || !!running}>
            {running ? tx("转写中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始转写")}
          </Button>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind={null}
            historyKind="subtitle,text"
            emptyHint={tx("上传音频，转写出文本和字幕")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              { label: tx("语言"), value: effectiveLanguage || tx("自动") },
              { label: tx("模型"), value: modelLabel },
              { label: tx("输出"), value: format || tx("自动") },
              { label: tx("文件"), value: file?.name ?? "" },
            ]}
          />
        }
      />
    </div>
  );
}

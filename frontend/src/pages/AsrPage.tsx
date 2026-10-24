import { useMutation, useQuery } from "@tanstack/react-query";
import { Mic } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
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

const ASR_MODEL_OPTIONS = [
  { value: "", label: "系统设置" },
  { value: "large-v3", label: "faster-whisper large-v3" },
  { value: "large-v3-turbo", label: "faster-whisper large-v3-turbo" },
  { value: "qwen3-asr-1.7b", label: "Qwen3-ASR-1.7B" },
];

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
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const asrProviders = providers?.filter((p) => p.enabled && p.capabilities.includes("asr"));

  const [providerId, setProviderId] = usePersistentState<number | "">("asr:provider", "");
  const provider = asrProviders?.find((p) => p.id === providerId) ?? asrProviders?.[0];
  const [language, setLanguage] = usePersistentState("asr:language", "");
  const [customLanguage, setCustomLanguage] = usePersistentState("asr:language-custom", "");
  const [format, setFormat] = usePersistentState("asr:format", "");
  const [asrModel, setAsrModel] = usePersistentState("asr:model", "");
  const effectiveLanguage = language === CUSTOM_LANG ? customLanguage.trim() : language;
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("asr");

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("file", file!);
      if (provider) form.set("provider_id", String(provider.id));
      if (effectiveLanguage) form.set("language", effectiveLanguage);
      if (format) form.set("formats", format);
      const chosenModel = asrModel || prefs?.default_asr_model || "";
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

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="asr" icon={Mic} title={tx("语音转文字")} description={tx("上传音频，导出文本和字幕。")} />
      <SplitPane
        storageKey="asr"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
            <Field label={tx("语言")} hint={tx("自动检测或选常用语言；其他语种选自定义后手动填写代码。")}>
              <select className={selectClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
                {LANGUAGE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {tx(o.label)}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={tx("识别模型")}
              hint={tx("不选则使用系统设置里的语音转文字模型。系统设置也未指定时，使用语音服务环境变量 LIBER_SPEECH_ASR_MODEL。")}
            >
              <select className={selectClass} value={asrModel} onChange={(e) => setAsrModel(e.target.value)}>
                {ASR_MODEL_OPTIONS.map((o) => (
                  <option key={o.value || "default"} value={o.value}>
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
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button onClick={() => submit.mutate()} disabled={!file || submit.isPending || !!running}>
              {running ? tx("转写中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始转写")}
            </Button>
          </div>
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
              { label: tx("模型"), value: asrModel || prefs?.default_asr_model || tx("系统设置") },
              { label: tx("输出"), value: format || tx("自动") },
              { label: tx("文件"), value: file?.name ?? "" },
            ]}
          />
        }
      />
    </div>
  );
}

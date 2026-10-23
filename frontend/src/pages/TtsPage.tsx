import { useMutation, useQuery } from "@tanstack/react-query";
import { AudioLines } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import { SpeechLanguageSelect, speechLanguage, useDefaultSpeechModel } from "@/components/SpeechLanguageSelect";
import { supportsTtsPreview, TtsPreview } from "@/components/TtsPreview";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";

export function TtsPage() {
  const tx = useTx();
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });
  const { data: ttsPacks } = useQuery({
    queryKey: ["workflows", "tts"],
    queryFn: () => api.listWorkflows("tts"),
  });

  // comfy 是工作流驱动的：没有 tts 包时不具备可用语音能力，不列出
  const ttsProviders = providers?.filter((p) => {
    if (!p.enabled || !p.capabilities.includes("tts")) return false;
    if (p.type === "comfyui") return (ttsPacks?.length ?? 0) > 0;
    return true;
  });

  const [providerId, setProviderId] = usePersistentState<number | "">("tts:provider", "");
  const provider = ttsProviders?.find((p) => p.id === providerId) ?? ttsProviders?.[0];
  const isComfy = provider?.type === "comfyui";
  const isSpeech = provider?.type === "liber_speech";
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("tts:voice-record", "");
  const [voiceName, setVoiceName] = usePersistentState("tts:voice-name", "");
  const [format, setFormat] = usePersistentState("tts:format", "mp3");
  const [language, setLanguage] = usePersistentState("tts:language", "");
  const [workflow, setWorkflow] = usePersistentState("tts:workflow", "");
  const pack = ttsPacks?.find((p) => p.name === workflow) ?? ttsPacks?.[0];
  const [extra, setExtra] = usePersistentState<Record<string, string>>("tts:extra", {});
  const location = useLocation();
  const incomingText = (location.state as { prompt?: string } | null)?.prompt;
  const [text, setText] = usePersistentState("tts:text", "");
  // 从其他页面带过来的文本优先于本地记忆
  useEffect(() => {
    if (incomingText) setText(incomingText);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const speechModel = useDefaultSpeechModel();
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("tts");

  const submit = useMutation({
    mutationFn: () =>
      api.submitTts({
        provider_id: provider?.id,
        voice_record_id: !isComfy && voiceRecordId !== "" ? voiceRecordId : undefined,
        voice: isComfy
          ? (extra.voice ?? "")
          : voiceRecordId !== ""
            ? undefined
            : isSpeech
              ? speechLanguage(voiceName, speechModel)
              : voiceName,
        text,
        format,
        options: isSpeech
          ? { language: speechLanguage(voiceRecordId === "" ? voiceName : language, speechModel) }
          : language
            ? { language }
            : undefined,
        workflow: isComfy ? pack?.name : undefined,
        inputs: isComfy
          ? Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== ""))
          : undefined,
      }),
    onSuccess: (j) => {
      setError(null);
      setJobId(j.id);
    },
    onError: (err) => setError(err.message),
  });

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader kind="tts" icon={AudioLines} title={tx("文字转语音")} description={tx("选择音色，把文本合成为语音文件。")} />
      <SplitPane
        storageKey="tts"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={tx("语音服务")} hint={tx("只列出已启用、且具备 tts 能力的 Provider。")}>
              <select
                className={selectClass}
                value={provider?.id ?? ""}
                onChange={(e) => setProviderId(Number(e.target.value))}
              >
                {ttsProviders?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            {!isComfy && (
              <Field
                label={tx("音色记录")}
                hint={
                  isSpeech
                    ? tx("选自音色库会克隆这条参考音频。不选则用模型自带的默认声音。")
                    : tx("选自音色库。不选则在下面手动填写音色名。")
                }
              >
                <select
                  className={selectClass}
                  value={voiceRecordId}
                  onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">{isSpeech ? tx("使用默认声音…") : tx("手动指定音色…")}</option>
                  {voices?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                      {v.is_default ? tx("（默认）") : ""}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {!isComfy && !isSpeech && (
              <Field label={tx("朗读语言")} hint={tx("只决定发音方式，不会把文字翻译成另一种语言。自动时，音色名以 zh、en 开头就用该语言，否则用中文。")}>
                <select className={selectClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="">{tx("自动")}</option>
                  <option value="zh">{tx("中文 zh")}</option>
                  <option value="en">{tx("英文 en")}</option>
                  <option value="ja">{tx("日文 ja")}</option>
                  <option value="ko">{tx("韩文 ko")}</option>
                  <option value="fr">{tx("法文 fr")}</option>
                  <option value="de">{tx("德文 de")}</option>
                  <option value="es">{tx("西班牙文 es")}</option>
                </select>
              </Field>
            )}
            {isComfy ? (
              <Field label={tx("语音工作流")} hint={tx("tts 能力的工作流包，朗读文本会自动注入。")}>
                <WorkflowPackControl name={pack?.name} description={pack?.description}>
                  <select
                    className={selectClass}
                    value={pack?.name ?? ""}
                    onChange={(e) => setWorkflow(e.target.value)}
                  >
                    {ttsPacks?.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </WorkflowPackControl>
              </Field>
            ) : (
              <Field label={tx("输出格式")} hint={tx("wav / ogg 需要兼容服务支持。")}>
                <select className={selectClass} value={format} onChange={(e) => setFormat(e.target.value)}>
                  <option value="mp3">mp3</option>
                  <option value="wav">wav</option>
                  <option value="ogg_opus">ogg_opus</option>
                </select>
              </Field>
            )}
          </div>
          {isComfy && ttsPacks && ttsPacks.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {tx('没有 tts 能力的工作流包，请到「设置 → 工作流包」导入。')}
            </p>
          )}
          {isComfy && pack && (
            <WorkflowInputs
              inputs={pack.inputs}
              values={extra}
              onChange={(k, v) => setExtra((prev) => ({ ...prev, [k]: v }))}
              exclude={["text"]}
              providerId={provider?.id}
            />
          )}
          {!isComfy && isSpeech && (
            <SpeechLanguageSelect
              value={voiceRecordId === "" ? voiceName : language}
              onChange={voiceRecordId === "" ? setVoiceName : setLanguage}
              model={speechModel}
            />
          )}
          {!isComfy && !isSpeech && voiceRecordId === "" && (
            <Field label={tx("音色名")} hint={tx("需与所选服务匹配，例如 zh、alloy、af_heart。")}>
              <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
            </Field>
          )}
          {supportsTtsPreview(provider?.type) && provider && (
            <TtsPreview
              providerId={provider.id}
              voice={
                voiceRecordId === ""
                  ? voiceName
                  : (voices?.find((v) => v.id === voiceRecordId)?.voice_id ||
                    voices?.find((v) => v.id === voiceRecordId)?.name ||
                    "")
              }
            />
          )}
          <Field label={tx("合成文本")} hint={tx("这段文字会按所选音色朗读。")}>
            <textarea
              className={`${areaClass} min-h-32`}
              placeholder={tx("输入要合成的文本…")}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate()}
              disabled={
                !text ||
                (!isComfy && !isSpeech && voiceRecordId === "" && !voiceName) ||
                (isComfy && !pack) ||
                submit.isPending ||
                !!running
              }
            >
              {running ? tx("合成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) }) : tx("开始合成")}
            </Button>
          </div>
        </CardContent>
      </Card>
        }
        right={
          <ResultPanel
            job={job ?? null}
            mediaKind="audio"
            historyKind="audio"
            emptyHint={tx("输入文本，合成第一段语音")}
            meta={[
              { label: tx("服务"), value: provider?.name ?? "" },
              {
                label: tx("音色"),
                value: isComfy
                  ? (pack?.name ?? "")
                  : voiceRecordId === ""
                    ? voiceName
                    : (voices?.find((v) => v.id === voiceRecordId)?.name ?? ""),
              },
              {
                label: tx("语言"),
                value: isSpeech
                  ? speechLanguage(voiceRecordId === "" ? voiceName : language, speechModel)
                  : language || tx("自动"),
              },
              { label: tx("格式"), value: format },
            ]}
          />
        }
      />
    </div>
  );
}

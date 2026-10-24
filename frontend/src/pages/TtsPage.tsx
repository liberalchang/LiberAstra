import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { api, type SpeechCatalogModel } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { ResultPanel } from "@/components/ResultPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SplitPane } from "@/components/ui/split-pane";
import {
  SPEECH_MODEL_GROUPS,
  SPEECH_MODELS,
  SpeechLanguageSelect,
  partitionServiceNames,
  sanitizeServiceVoice,
  speechLanguage,
  useDefaultSpeechModel,
} from "@/components/SpeechLanguageSelect";
import { supportsTtsPreview, TtsPreview } from "@/components/TtsPreview";
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { WorkflowPackControl } from "@/components/WorkflowPackHint";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTx } from "@/i18n/tx";

export function TtsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
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
  const kind = provider?.type;
  const isComfy = kind === "comfyui";
  const isSpeech = kind === "liber_speech";
  const isEdge = kind === "edge_tts";
  const isOpenAi = kind === "openai_tts";
  const [voiceRecordId, setVoiceRecordId] = usePersistentState<number | "">("tts:voice-record", "");
  const [voiceName, setVoiceName] = usePersistentState("tts:voice-name", "");
  const [speechLang, setSpeechLang] = usePersistentState("tts:speech-lang", "zh");
  const [format, setFormat] = usePersistentState("tts:format", "mp3");
  const [ttsModel, setTtsModel] = usePersistentState("tts:model", "");
  const [openAiModel, setOpenAiModel] = usePersistentState("tts:openai-model", "");
  const [openAiVoiceManual, setOpenAiVoiceManual] = usePersistentState("tts:openai-voice-manual", false);
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
  const chosenSpeechModel = ttsModel || speechModel;
  const { data: speechCatalog } = useQuery({
    queryKey: ["speech-catalog"],
    queryFn: api.getSpeechCatalog,
    enabled: isSpeech,
    retry: false,
  });
  const ttsModelOptions = speechCatalog?.tts_models?.length
    ? speechCatalog.tts_models
    : SPEECH_MODELS;
  const refreshModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  const serviceNames = provider?.models ?? [];
  const openAiSplit = partitionServiceNames(isOpenAi ? serviceNames : []);
  const edgeVoices = isEdge ? serviceNames : [];
  const openAiVoices = openAiSplit.voices;
  const openAiModels = openAiSplit.models;
  const cloudVoices = voices?.filter((item) => item.voice_id) ?? [];

  // 切到本地或 OpenAI 兼容时拉一次音色/模型，并清掉误写入的语言码
  useEffect(() => {
    if (!provider || isComfy || isSpeech) return;
    if (serviceNames.length === 0 && !refreshModels.isPending) {
      refreshModels.mutate(provider.id);
    }
    if (isEdge && format !== "mp3") setFormat("mp3");
    const nextVoice = isEdge
      ? sanitizeServiceVoice(voiceName, edgeVoices, "edge_tts")
      : isOpenAi
        ? sanitizeServiceVoice(voiceName, openAiVoices, "openai_tts")
        : voiceName;
    if (nextVoice !== voiceName) setVoiceName(nextVoice);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider?.id, provider?.type, serviceNames.join("|")]);

  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("tts");
  const spokenLanguage = speechLanguage(speechLang, chosenSpeechModel);
  const selectedLibrary = voices?.find((item) => item.id === voiceRecordId);

  const submit = useMutation({
    mutationFn: () =>
      api.submitTts({
        provider_id: provider?.id,
        voice_record_id:
          !isComfy && !isEdge && voiceRecordId !== "" ? voiceRecordId : undefined,
        voice: isComfy
          ? (extra.voice ?? "")
          : !isEdge && voiceRecordId !== ""
            ? undefined
            : isSpeech
              ? spokenLanguage
              : voiceName,
        text,
        format: isEdge ? "mp3" : format,
        model: isSpeech && ttsModel ? ttsModel : isOpenAi && openAiModel ? openAiModel : undefined,
        options: isSpeech ? { language: spokenLanguage } : undefined,
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
  const previewVoice =
    isOpenAi && voiceRecordId !== ""
      ? (selectedLibrary?.voice_id || selectedLibrary?.name || "")
      : voiceName;

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
            {isSpeech && (
              <Field
                label={tx("文字转语音模型")}
                hint={tx("不选则使用系统设置里的文字转语音模型。")}
              >
                <select className={selectClass} value={ttsModel} onChange={(e) => setTtsModel(e.target.value)}>
                  <option value="">{tx("系统设置")}</option>
                  {groupTtsModels(ttsModelOptions).map((group) => (
                    <optgroup key={group.id || "other"} label={tx(speechGroupLabel(group.id))}>
                      {group.items.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </Field>
            )}
            {isOpenAi && (
              <Field label={tx("文字转语音模型")} hint={tx("不选则使用该服务的默认模型 tts-1。")}>
                <div className="flex gap-2">
                  {openAiModels.length > 0 ? (
                    <select
                      className={selectClass}
                      value={openAiModel}
                      onChange={(e) => setOpenAiModel(e.target.value)}
                    >
                      <option value="">{tx("默认 (tts-1)")}</option>
                      {openAiModels.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder={refreshModels.isPending ? tx("正在从服务拉取模型…") : "tts-1"}
                      value={openAiModel}
                      onChange={(e) => setOpenAiModel(e.target.value)}
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
              </Field>
            )}
            {isEdge && (
              <Field
                label={tx("音色")}
                hint={tx("本地音色来自微软 Edge TTS。语言由音色名决定，不支持参考音频克隆。")}
              >
                <div className="flex gap-2">
                  {edgeVoices.length > 0 ? (
                    <select
                      className={selectClass}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    >
                      {edgeVoices.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder={refreshModels.isPending ? tx("正在从服务拉取音色…") : "zh-CN-XiaoxiaoNeural"}
                      value={voiceName}
                      onChange={(e) => setVoiceName(e.target.value)}
                    />
                  )}
                  <Button
                    variant="outline"
                    size="icon"
                    title={tx("从服务拉取音色列表")}
                    disabled={!provider || refreshModels.isPending}
                    onClick={() => provider && refreshModels.mutate(provider.id)}
                  >
                    <RefreshCw />
                  </Button>
                </div>
              </Field>
            )}
            {isComfy && (
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
            )}
            {(isSpeech || isOpenAi) && (
              <Field
                label={tx("音色记录")}
                hint={
                  isSpeech
                    ? tx("选自音色库会克隆这条参考音频。不选则用模型自带的默认声音。")
                    : tx("选自音色库时使用其中的 voice_id。不选则在下面填写音色名。")
                }
              >
                <select
                  className={selectClass}
                  value={voiceRecordId}
                  onChange={(e) => setVoiceRecordId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">{isSpeech ? tx("使用默认声音…") : tx("手动指定音色…")}</option>
                  {(isOpenAi ? cloudVoices : voices)?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                      {v.is_default ? tx("（默认）") : ""}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {!isComfy && (
              <Field
                label={tx("输出格式")}
                hint={isEdge ? tx("仅 mp3。本地 Edge TTS 不输出 wav / ogg。") : tx("wav / ogg 需要兼容服务支持。")}
              >
                <select
                  className={selectClass}
                  value={isEdge ? "mp3" : format}
                  onChange={(e) => setFormat(e.target.value)}
                  disabled={isEdge}
                >
                  <option value="mp3">mp3</option>
                  {!isEdge && <option value="wav">wav</option>}
                  {!isEdge && <option value="ogg_opus">ogg_opus</option>}
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
          {isSpeech && (
            <SpeechLanguageSelect
              value={speechLang}
              onChange={setSpeechLang}
              model={chosenSpeechModel}
            />
          )}
          {isOpenAi && voiceRecordId === "" && (
            <Field label={tx("音色名")} hint={tx("来自该服务的音色列表，也可手动输入，例如 alloy。")}>
              <div className="flex gap-2">
                {openAiVoices.length > 0 && !openAiVoiceManual ? (
                  <select
                    className={selectClass}
                    value={openAiVoices.includes(voiceName) ? voiceName : ""}
                    onChange={(e) => {
                      if (e.target.value === "__manual") {
                        setOpenAiVoiceManual(true);
                        return;
                      }
                      setVoiceName(e.target.value);
                    }}
                  >
                    <option value="">{tx("选择音色…")}</option>
                    {openAiVoices.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                    <option value="__manual">{tx("手动输入音色…")}</option>
                  </select>
                ) : (
                  <Input
                    placeholder="alloy"
                    value={voiceName}
                    onChange={(e) => setVoiceName(e.target.value)}
                  />
                )}
                {openAiVoices.length > 0 && openAiVoiceManual && (
                  <Button variant="outline" onClick={() => setOpenAiVoiceManual(false)}>
                    {tx("从列表选择")}
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="icon"
                  title={tx("从服务拉取音色列表")}
                  disabled={!provider || refreshModels.isPending}
                  onClick={() => provider && refreshModels.mutate(provider.id)}
                >
                  <RefreshCw />
                </Button>
              </div>
            </Field>
          )}
          {supportsTtsPreview(provider?.type) && provider && (
            <TtsPreview providerId={provider.id} voice={previewVoice} />
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
                (isEdge && !voiceName) ||
                (isOpenAi && voiceRecordId === "" && !voiceName) ||
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
              ...(isSpeech
                ? [{ label: tx("模型"), value: ttsModel || tx("系统设置") }]
                : isOpenAi
                  ? [{ label: tx("模型"), value: openAiModel || "tts-1" }]
                  : []),
              {
                label: tx("音色"),
                value: isComfy
                  ? (pack?.name ?? "")
                  : !isEdge && voiceRecordId !== ""
                    ? (selectedLibrary?.name ?? "")
                    : isSpeech
                      ? spokenLanguage
                      : voiceName,
              },
              ...(isSpeech ? [{ label: tx("语言"), value: spokenLanguage }] : []),
              ...(!isComfy ? [{ label: tx("格式"), value: isEdge ? "mp3" : format }] : []),
            ]}
          />
        }
      />
    </div>
  );
}

function speechGroupLabel(group: string): string {
  return SPEECH_MODEL_GROUPS.find((item) => item.id === group)?.label || group || "其他";
}

function groupTtsModels(models: SpeechCatalogModel[]) {
  const order: string[] = [];
  const grouped = new Map<string, SpeechCatalogModel[]>();
  for (const item of models) {
    const group = item.group || "";
    if (!grouped.has(group)) {
      order.push(group);
      grouped.set(group, []);
    }
    grouped.get(group)?.push(item);
  }
  return order.map((id) => ({ id, items: grouped.get(id) ?? [] }));
}

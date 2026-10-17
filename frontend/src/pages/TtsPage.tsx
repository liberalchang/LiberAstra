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
import { WorkflowInputs } from "@/components/WorkflowInputs";
import { useTrackedJob } from "@/hooks/useJob";
import { usePersistentState } from "@/hooks/usePersistentState";

export function TtsPage() {
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
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("tts");

  const submit = useMutation({
    mutationFn: () =>
      api.submitTts({
        provider_id: provider?.id,
        voice_record_id: !isComfy && voiceRecordId !== "" ? voiceRecordId : undefined,
        voice: isComfy ? (extra.voice ?? "") : voiceRecordId === "" ? voiceName : undefined,
        text,
        format,
        options: language ? { language } : undefined,
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
      <PageHeader kind="tts" icon={AudioLines} title="文字转语音" description="选择音色，把文本合成为语音文件。" />
      <SplitPane
        storageKey="tts"
        left={
      <Card>
        <CardContent className="flex flex-col gap-4 pt-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="语音服务" hint="只列出已启用、且具备 tts 能力的 Provider。">
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
              <Field label="音色记录" hint="选自音色库。不选则在下面手动填写音色名。">
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
            )}
            {!isComfy && (
              <Field label="朗读语言" hint="只决定发音方式，不会把文字翻译成另一种语言。自动时，音色名以 zh、en 开头就用该语言，否则用中文。">
                <select className={selectClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="">自动</option>
                  <option value="zh">中文 zh</option>
                  <option value="en">英文 en</option>
                  <option value="ja">日文 ja</option>
                  <option value="ko">韩文 ko</option>
                  <option value="fr">法文 fr</option>
                  <option value="de">德文 de</option>
                  <option value="es">西班牙文 es</option>
                </select>
              </Field>
            )}
            {isComfy ? (
              <Field label="语音工作流" hint="tts 能力的工作流包，朗读文本会自动注入。">
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
              </Field>
            ) : (
              <Field label="输出格式" hint="wav / ogg 需要兼容服务支持。">
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
              没有 tts 能力的工作流包，请到「设置 → 工作流包」导入。
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
          {!isComfy && voiceRecordId === "" && (
            <Field label="音色名" hint="需与所选服务匹配，例如 zh、alloy、af_heart。">
              <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
            </Field>
          )}
          <Field label="合成文本" hint="这段文字会按所选音色朗读。">
            <textarea
              className={`${areaClass} min-h-32`}
              placeholder="输入要合成的文本…"
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
                (!isComfy && voiceRecordId === "" && !voiceName) ||
                (isComfy && !pack) ||
                submit.isPending ||
                !!running
              }
            >
              {running ? `合成中… ${Math.round((job?.progress ?? 0) * 100)}%` : "开始合成"}
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
            emptyHint="输入文本，合成第一段语音"
            meta={[
              { label: "服务", value: provider?.name ?? "" },
              {
                label: "音色",
                value: isComfy
                  ? (pack?.name ?? "")
                  : voiceRecordId === ""
                    ? voiceName
                    : (voices?.find((v) => v.id === voiceRecordId)?.name ?? ""),
              },
              { label: "语言", value: language || "自动" },
              { label: "格式", value: format },
            ]}
          />
        }
      />
    </div>
  );
}

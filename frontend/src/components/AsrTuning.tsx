import { RotateCcw } from "lucide-react";

import { Switch, TuningSection } from "@/components/SpeechControls";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";
import {
  DEFAULT_ASR_TUNING,
  type AsrTask,
  type AsrTimestamps,
  type AsrTuning as AsrTuningValue,
  asrModelKind,
} from "@/lib/asrTuning";

function extraError(value: string, tx: (text: string) => string): string {
  if (!value.trim()) return "";
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? ""
      : tx("附加参数必须是 JSON 对象");
  } catch {
    return tx("JSON 格式不正确");
  }
}

export function AsrTuning({
  value,
  onChange,
  model,
}: {
  value: AsrTuningValue;
  onChange: (value: AsrTuningValue) => void;
  model: string | null | undefined;
}) {
  const tx = useTx();
  const update = (patch: Partial<AsrTuningValue>) => onChange({ ...value, ...patch });
  const qwen = asrModelKind(model) === "qwen";
  const invalidExtra = extraError(value.extraJson, tx);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-3">
      <Switch
        label={tx("高级参数")}
        hint={tx("调整时间戳、VAD、热词与解码参数；关闭时使用服务默认值。")}
        checked={value.advanced}
        onChange={(advanced) => update({ advanced })}
      />

      {value.advanced && (
        <div className="flex flex-col gap-4 border-t border-border pt-3">
          {qwen && (
            <p className="text-xs text-muted-foreground">
              {tx("Qwen3-ASR 不支持 VAD、beam、热词和初始提示词；这些选项已隐藏。")}
            </p>
          )}

          <TuningSection title={tx("识别")}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("时间戳")} hint={tx("词级时间戳会额外返回 words。")}>
                <select
                  className={selectClass}
                  value={value.timestamps}
                  onChange={(e) => update({ timestamps: e.target.value as AsrTimestamps })}
                >
                  <option value="none">{tx("不返回")}</option>
                  <option value="segment">{tx("分段")}</option>
                  <option value="word">{tx("词级")}</option>
                </select>
              </Field>
              <Field label={tx("任务")} hint={tx("翻译仅 Whisper 支持。")}>
                {qwen ? (
                  <select className={selectClass} value="transcribe" disabled>
                    <option value="transcribe">{tx("转写")}</option>
                  </select>
                ) : (
                  <select
                    className={selectClass}
                    value={value.task}
                    onChange={(e) => update({ task: e.target.value as AsrTask })}
                  >
                    <option value="transcribe">{tx("转写")}</option>
                    <option value="translate">{tx("翻译成英文")}</option>
                  </select>
                )}
              </Field>
            </div>
            {!qwen && (
              <Switch
                label={tx("VAD 去静音")}
                hint={tx("先用 Silero VAD 去掉非语音段，再识别。")}
                checked={value.vad}
                onChange={(vad) => update({ vad })}
              />
            )}
            {!qwen && (
              <Field label={tx("热词")} hint={tx("用逗号或空格分隔人名、术语，提升识别率。")}>
                <Input
                  value={value.hotwords}
                  placeholder={tx("如：LiberAstra, 张三")}
                  onChange={(e) => update({ hotwords: e.target.value })}
                />
              </Field>
            )}
            {!qwen && (
              <Field label={tx("初始提示词")} hint={tx("给模型提供术语、标点或上下文风格。")}>
                <textarea
                  className={`${areaClass} min-h-20`}
                  value={value.initialPrompt}
                  placeholder={tx("如：以下内容包含产品名 LiberAstra 和人名…")}
                  onChange={(e) => update({ initialPrompt: e.target.value })}
                />
              </Field>
            )}
            {!qwen && (
              <Switch
                label={tx("上文作为上下文")}
                hint={tx("关闭可减少长音频中的重复与串词。")}
                checked={value.conditionOnPreviousText}
                onChange={(conditionOnPreviousText) => update({ conditionOnPreviousText })}
              />
            )}
          </TuningSection>

          {qwen ? (
            <TuningSection title={tx("Qwen 推理")}>
              <Field label={tx("推理批大小")} hint={tx("1–32；显存不足时调小。")}>
                <Input
                  type="number"
                  min={1}
                  max={32}
                  value={value.qwenBatchSize}
                  onChange={(e) => update({ qwenBatchSize: Number(e.target.value) })}
                />
              </Field>
            </TuningSection>
          ) : (
            <TuningSection title={tx("解码")}>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("Beam 宽度")} hint={tx("1–10，越大越稳但越慢。")}>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={value.beamSize}
                    onChange={(e) => update({ beamSize: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("候选数")} hint={tx("采样时保留的候选数量，1–10。")}>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={value.bestOf}
                    onChange={(e) => update({ bestOf: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("静音阈值")} hint={tx("0–1，越高越容易判为非语音。")}>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={value.noSpeechThreshold}
                    onChange={(e) => update({ noSpeechThreshold: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("压缩比阈值")} hint={tx("过滤重复和幻觉，常用 2.4。")}>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    value={value.compressionRatioThreshold}
                    onChange={(e) =>
                      update({ compressionRatioThreshold: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
              <Field
                label={tx("温度回退")}
                hint={tx("逗号分隔；前一个温度失败时依次尝试后面的温度。")}
              >
                <Input
                  value={value.temperature}
                  placeholder="0, 0.2, 0.4, 0.6"
                  onChange={(e) => update({ temperature: e.target.value })}
                />
              </Field>
            </TuningSection>
          )}

          <Field
            label={tx("附加参数 JSON")}
            hint={invalidExtra || tx("可填写上述控件未覆盖的语音服务参数。")}
          >
            <textarea
              className={`${areaClass} min-h-16 font-mono text-xs`}
              value={value.extraJson}
              placeholder='{"suppress_blank": true}'
              onChange={(e) => update({ extraJson: e.target.value })}
            />
          </Field>
          {invalidExtra ? <p className="text-xs text-danger">{invalidExtra}</p> : null}

          <button
            type="button"
            onClick={() => onChange({ ...DEFAULT_ASR_TUNING })}
            className="flex w-fit items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3.5" />
            {tx("恢复默认")}
          </button>
        </div>
      )}
    </div>
  );
}

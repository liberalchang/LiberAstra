import { RotateCcw } from "lucide-react";

import { Switch, TuningSection } from "@/components/SpeechControls";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";
import {
  DEFAULT_VC_TUNING,
  type VcTuning as VcTuningValue,
  vcModelKind,
} from "@/lib/vcTuning";

const SAMPLE_RATES = [0, 16000, 22050, 24000, 44100, 48000];

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

export function VcTuning({
  value,
  onChange,
  model,
}: {
  value: VcTuningValue;
  onChange: (value: VcTuningValue) => void;
  model: string | null | undefined;
}) {
  const tx = useTx();
  const update = (patch: Partial<VcTuningValue>) => onChange({ ...value, ...patch });
  const seedVc = vcModelKind(model) === "seedvc";
  const invalidExtra = extraError(value.extraJson, tx);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-3">
      <Switch
        label={tx("换音高级参数")}
        hint={tx("调整替换范围、响度、降噪与模型生成参数；关闭时使用服务默认值。")}
        checked={value.advanced}
        onChange={(advanced) => update({ advanced })}
      />

      {value.advanced && (
        <div className="flex flex-col gap-4 border-t border-border pt-3">
          <TuningSection title={tx("替换范围")}>
            <Switch
              label={tx("整段替换")}
              hint={tx("忽略识别出的语音分段，整条音轨都换音。")}
              checked={value.convertAll}
              onChange={(convertAll) => update({ convertAll })}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("分段前后扩展")} hint={tx("秒；给分段边缘留缓冲。")}>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={value.segmentPadding}
                  onChange={(e) => update({ segmentPadding: Number(e.target.value) })}
                />
              </Field>
              <Field label={tx("分段合并间隔")} hint={tx("秒；间隔小于该值的相邻分段会合并。")}>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={value.mergeGap}
                  onChange={(e) => update({ mergeGap: Number(e.target.value) })}
                />
              </Field>
              <Field label={tx("最短分段")} hint={tx("秒；过短的分段会被跳过。")}>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={value.minSegment}
                  onChange={(e) => update({ minSegment: Number(e.target.value) })}
                />
              </Field>
            </div>
          </TuningSection>

          <TuningSection title={tx("响度与清理")}>
            <Switch
              label={tx("响度归一")}
              hint={tx("用 loudnorm 统一输出响度。")}
              checked={value.normalizeLoudness}
              onChange={(normalizeLoudness) => update({ normalizeLoudness })}
            />
            {value.normalizeLoudness && (
              <Field label={tx("目标响度")} hint={tx("LUFS，常用 -16；范围 -40 到 -5。")}>
                <Input
                  type="number"
                  min={-40}
                  max={-5}
                  step={0.5}
                  value={value.targetLufs}
                  onChange={(e) => update({ targetLufs: Number(e.target.value) })}
                />
              </Field>
            )}
            <Switch
              label={tx("底噪清理")}
              hint={tx("用 ffmpeg afftdn 去底噪；可能削弱呼吸声。")}
              checked={value.denoise}
              onChange={(denoise) => update({ denoise })}
            />
            <Field label={tx("输出采样率")} hint={tx("跟随源文件，或指定 16k–48k。")}>
              <select
                className={selectClass}
                value={value.outputSampleRate}
                onChange={(e) => update({ outputSampleRate: Number(e.target.value) })}
              >
                {SAMPLE_RATES.map((rate) => (
                  <option key={rate} value={rate}>
                    {rate === 0 ? tx("跟随源文件") : `${rate} Hz`}
                  </option>
                ))}
              </select>
            </Field>
          </TuningSection>

          <TuningSection title={tx("参考音频")}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("起点")} hint={tx("秒；从参考音频的该位置开始截取。")}>
                <Input
                  type="number"
                  min={0}
                  step={0.1}
                  value={value.refStart}
                  onChange={(e) => update({ refStart: Number(e.target.value) })}
                />
              </Field>
              <Field label={tx("使用时长")} hint={tx("0 表示用到模型上限。")}>
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  value={value.refDuration}
                  onChange={(e) => update({ refDuration: Number(e.target.value) })}
                />
              </Field>
            </div>
            {seedVc ? (
              <Field label={tx("参考音频最大长度")} hint={tx("Seed-VC 默认最多 25 秒。")}>
                <Input
                  type="number"
                  min={5}
                  max={30}
                  step={0.5}
                  value={value.refMaxLen}
                  onChange={(e) => update({ refMaxLen: Number(e.target.value) })}
                />
              </Field>
            ) : (
              <p className="text-xs text-muted-foreground">
                {tx("Chatterbox VC 只使用参考音频前 10 秒；可用起点和时长选择片段。")}
              </p>
            )}
          </TuningSection>

          {seedVc && (
            <TuningSection title={tx("Seed-VC 生成")}>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={tx("随机种子")} hint={tx("相同种子便于复现；0 也有效。")}>
                  <Input
                    type="number"
                    min={0}
                    value={value.seed}
                    onChange={(e) => update({ seed: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("Diffusion 步数")} hint={tx("1–50；越多越慢。")}>
                  <Input
                    type="number"
                    min={1}
                    max={50}
                    value={value.diffusionSteps}
                    onChange={(e) => update({ diffusionSteps: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("CFG 强度")} hint={tx("0–2；越高越贴近音色，过高可能失真。")}>
                  <Input
                    type="number"
                    min={0}
                    max={2}
                    step={0.05}
                    value={value.inferenceCfgRate}
                    onChange={(e) => update({ inferenceCfgRate: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("量化器数量")} hint={tx("1–8；影响音质与显存。")}>
                  <Input
                    type="number"
                    min={1}
                    max={8}
                    value={value.nQuantizers}
                    onChange={(e) => update({ nQuantizers: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("采样温度")} hint={tx("0.1–2；越高变化越大。")}>
                  <Input
                    type="number"
                    min={0.1}
                    max={2}
                    step={0.05}
                    value={value.temperature}
                    onChange={(e) => update({ temperature: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("时间轴缩放")} hint={tx("0.9–1.1；换音建议保持 1.0。")}>
                  <Input
                    type="number"
                    min={0.9}
                    max={1.1}
                    step={0.01}
                    value={value.lengthAdjust}
                    onChange={(e) => update({ lengthAdjust: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("分块重叠帧")} hint={tx("4–64；影响接缝平滑度。")}>
                  <Input
                    type="number"
                    min={4}
                    max={64}
                    value={value.overlapFrameLen}
                    onChange={(e) => update({ overlapFrameLen: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("窗口长度")} hint={tx("5–30 秒；越长越吃显存。")}>
                  <Input
                    type="number"
                    min={5}
                    max={30}
                    step={0.5}
                    value={value.maxWindow}
                    onChange={(e) => update({ maxWindow: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("接缝上下文")} hint={tx("0–0.5 秒；用于跨段衔接。")}>
                  <Input
                    type="number"
                    min={0}
                    max={0.5}
                    step={0.01}
                    value={value.context}
                    onChange={(e) => update({ context: Number(e.target.value) })}
                  />
                </Field>
                <Field label={tx("接缝淡入淡出")} hint={tx("0–0.1 秒；减少爆音。")}>
                  <Input
                    type="number"
                    min={0}
                    max={0.1}
                    step={0.01}
                    value={value.fade}
                    onChange={(e) => update({ fade: Number(e.target.value) })}
                  />
                </Field>
              </div>
            </TuningSection>
          )}

          <Field
            label={tx("附加参数 JSON")}
            hint={invalidExtra || tx("可填写上述控件未覆盖的语音服务参数。")}
          >
            <textarea
              className={`${areaClass} min-h-16 font-mono text-xs`}
              value={value.extraJson}
              placeholder='{"pitch": 0}'
              onChange={(e) => update({ extraJson: e.target.value })}
            />
          </Field>
          {invalidExtra ? <p className="text-xs text-danger">{invalidExtra}</p> : null}

          <button
            type="button"
            onClick={() => onChange({ ...DEFAULT_VC_TUNING })}
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

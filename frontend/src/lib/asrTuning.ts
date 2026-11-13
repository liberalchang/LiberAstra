export type AsrTimestamps = "none" | "segment" | "word";
export type AsrTask = "transcribe" | "translate";

export interface AsrTuning {
  advanced: boolean;
  timestamps: AsrTimestamps;
  task: AsrTask;
  vad: boolean;
  beamSize: number;
  bestOf: number;
  /** 逗号分隔的温度回退列表；语音服务接受数字数组。 */
  temperature: string;
  noSpeechThreshold: number;
  compressionRatioThreshold: number;
  conditionOnPreviousText: boolean;
  initialPrompt: string;
  hotwords: string;
  qwenBatchSize: number;
  extraJson: string;
}

export const DEFAULT_ASR_TUNING: AsrTuning = {
  advanced: false,
  timestamps: "segment",
  task: "transcribe",
  vad: false,
  beamSize: 5,
  bestOf: 5,
  temperature: "0, 0.2, 0.4, 0.6, 0.8, 1.0",
  noSpeechThreshold: 0.6,
  compressionRatioThreshold: 2.4,
  conditionOnPreviousText: true,
  initialPrompt: "",
  hotwords: "",
  qwenBatchSize: 4,
  extraJson: "",
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
const clampInt = (value: unknown, min: number, max: number, fallback: number) => {
  const number = Number(value);
  return Math.min(max, Math.max(min, Number.isFinite(number) ? Math.round(number) : fallback));
};
const clampFloat = (value: unknown, min: number, max: number, fallback: number) => {
  const number = Number(value);
  return clamp(Number.isFinite(number) ? number : fallback, min, max);
};

export function normalizeAsrTuning(raw: unknown): AsrTuning {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_ASR_TUNING };
  const data = raw as Partial<AsrTuning>;
  const timestamps: AsrTimestamps = ["none", "segment", "word"].includes(
    String(data.timestamps),
  )
    ? (data.timestamps as AsrTimestamps)
    : DEFAULT_ASR_TUNING.timestamps;
  const task: AsrTask =
    data.task === "translate" ? "translate" : DEFAULT_ASR_TUNING.task;
  return {
    advanced: Boolean(data.advanced),
    timestamps,
    task,
    vad: Boolean(data.vad),
    beamSize: clampInt(data.beamSize, 1, 10, DEFAULT_ASR_TUNING.beamSize),
    bestOf: clampInt(data.bestOf, 1, 10, DEFAULT_ASR_TUNING.bestOf),
    temperature:
      typeof data.temperature === "string"
        ? data.temperature
            .split(",")
            .map((item) => item.trim())
            .filter((item) => Number.isFinite(Number(item)))
            .join(", ")
        : DEFAULT_ASR_TUNING.temperature,
    noSpeechThreshold: clampFloat(
      data.noSpeechThreshold,
      0,
      1,
      DEFAULT_ASR_TUNING.noSpeechThreshold,
    ),
    compressionRatioThreshold: clampFloat(
      data.compressionRatioThreshold,
      0,
      10,
      DEFAULT_ASR_TUNING.compressionRatioThreshold,
    ),
    conditionOnPreviousText:
      data.conditionOnPreviousText === undefined
        ? DEFAULT_ASR_TUNING.conditionOnPreviousText
        : Boolean(data.conditionOnPreviousText),
    initialPrompt: typeof data.initialPrompt === "string" ? data.initialPrompt : "",
    hotwords: typeof data.hotwords === "string" ? data.hotwords : "",
    qwenBatchSize: clampInt(
      data.qwenBatchSize,
      1,
      32,
      DEFAULT_ASR_TUNING.qwenBatchSize,
    ),
    extraJson: typeof data.extraJson === "string" ? data.extraJson : "",
  };
}

export function asrModelKind(model: string | null | undefined): "whisper" | "qwen" {
  return (model || "").toLowerCase().includes("qwen") ? "qwen" : "whisper";
}

function parseExtra(value: string): Record<string, unknown> {
  if (!value.trim()) return {};
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function temperatureList(value: string): number[] | null {
  const numbers = value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
  return numbers.length ? numbers.map((item) => Math.round(item * 1000) / 1000) : null;
}

export function asrOptions(
  tuning: AsrTuning,
  model: string | null | undefined,
): Record<string, unknown> {
  if (!tuning.advanced) return {};
  const kind = asrModelKind(model);
  const options: Record<string, unknown> = {};

  if (["none", "segment", "word"].includes(tuning.timestamps)) {
    options.timestamps = tuning.timestamps;
  }
  if (kind === "qwen") {
    options.max_inference_batch_size = tuning.qwenBatchSize;
  } else {
    if (tuning.task === "translate") options.task = "translate";
    if (tuning.vad) options.vad_filter = true;
    options.beam_size = tuning.beamSize;
    options.best_of = tuning.bestOf;
    const temperature = temperatureList(tuning.temperature);
    if (temperature) options.temperature = temperature;
    options.no_speech_threshold = tuning.noSpeechThreshold;
    options.compression_ratio_threshold = tuning.compressionRatioThreshold;
    if (!tuning.conditionOnPreviousText) options.condition_on_previous_text = false;
    if (tuning.initialPrompt.trim()) options.initial_prompt = tuning.initialPrompt.trim();
    if (tuning.hotwords.trim()) options.hotwords = tuning.hotwords.trim();
  }

  return { ...options, ...parseExtra(tuning.extraJson) };
}

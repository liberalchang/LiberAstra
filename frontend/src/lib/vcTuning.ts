export interface VcTuning {
  advanced: boolean;
  convertAll: boolean;
  segmentPadding: number;
  mergeGap: number;
  minSegment: number;
  normalizeLoudness: boolean;
  targetLufs: number;
  denoise: boolean;
  outputSampleRate: number;
  refStart: number;
  refDuration: number;
  seed: number;
  diffusionSteps: number;
  inferenceCfgRate: number;
  nQuantizers: number;
  temperature: number;
  lengthAdjust: number;
  overlapFrameLen: number;
  maxWindow: number;
  context: number;
  fade: number;
  refMaxLen: number;
  extraJson: string;
}

export const DEFAULT_VC_TUNING: VcTuning = {
  advanced: false,
  convertAll: false,
  segmentPadding: 0,
  mergeGap: 0.05,
  minSegment: 0.02,
  normalizeLoudness: false,
  targetLufs: -16,
  denoise: false,
  outputSampleRate: 0,
  refStart: 0,
  refDuration: 0,
  seed: 0,
  diffusionSteps: 10,
  inferenceCfgRate: 0.7,
  nQuantizers: 3,
  temperature: 1,
  lengthAdjust: 1,
  overlapFrameLen: 16,
  maxWindow: 20,
  context: 0.15,
  fade: 0.02,
  refMaxLen: 25,
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

export function normalizeVcTuning(raw: unknown): VcTuning {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_VC_TUNING };
  const data = raw as Partial<VcTuning>;
  return {
    advanced: Boolean(data.advanced),
    convertAll: Boolean(data.convertAll),
    segmentPadding: clampFloat(
      data.segmentPadding,
      0,
      3600,
      DEFAULT_VC_TUNING.segmentPadding,
    ),
    mergeGap: clampFloat(data.mergeGap, 0, 3600, DEFAULT_VC_TUNING.mergeGap),
    minSegment: clampFloat(data.minSegment, 0, 3600, DEFAULT_VC_TUNING.minSegment),
    normalizeLoudness: Boolean(data.normalizeLoudness),
    targetLufs: clampFloat(data.targetLufs, -40, -5, DEFAULT_VC_TUNING.targetLufs),
    denoise: Boolean(data.denoise),
    outputSampleRate: clampInt(
      data.outputSampleRate,
      0,
      192000,
      DEFAULT_VC_TUNING.outputSampleRate,
    ),
    refStart: clampFloat(data.refStart, 0, 3600, DEFAULT_VC_TUNING.refStart),
    refDuration: clampFloat(data.refDuration, 0, 3600, DEFAULT_VC_TUNING.refDuration),
    seed: clampInt(data.seed, 0, 2147483647, DEFAULT_VC_TUNING.seed),
    diffusionSteps: clampInt(
      data.diffusionSteps,
      1,
      50,
      DEFAULT_VC_TUNING.diffusionSteps,
    ),
    inferenceCfgRate: clampFloat(
      data.inferenceCfgRate,
      0,
      2,
      DEFAULT_VC_TUNING.inferenceCfgRate,
    ),
    nQuantizers: clampInt(data.nQuantizers, 1, 8, DEFAULT_VC_TUNING.nQuantizers),
    temperature: clampFloat(data.temperature, 0.1, 2, DEFAULT_VC_TUNING.temperature),
    lengthAdjust: clampFloat(data.lengthAdjust, 0.9, 1.1, DEFAULT_VC_TUNING.lengthAdjust),
    overlapFrameLen: clampInt(
      data.overlapFrameLen,
      4,
      64,
      DEFAULT_VC_TUNING.overlapFrameLen,
    ),
    maxWindow: clampFloat(data.maxWindow, 5, 30, DEFAULT_VC_TUNING.maxWindow),
    context: clampFloat(data.context, 0, 0.5, DEFAULT_VC_TUNING.context),
    fade: clampFloat(data.fade, 0, 0.1, DEFAULT_VC_TUNING.fade),
    refMaxLen: clampFloat(data.refMaxLen, 5, 30, DEFAULT_VC_TUNING.refMaxLen),
    extraJson: typeof data.extraJson === "string" ? data.extraJson : "",
  };
}

export function vcModelKind(model: string | null | undefined): "chatterbox" | "seedvc" {
  return (model || "").toLowerCase().includes("seed") ? "seedvc" : "chatterbox";
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

const round = (value: number) => Math.round(value * 1000) / 1000;

export function vcOptions(
  tuning: VcTuning,
  model: string | null | undefined,
): Record<string, unknown> {
  if (!tuning.advanced) return {};
  const kind = vcModelKind(model);
  const options: Record<string, unknown> = {};

  if (tuning.convertAll) options.convert_all = true;
  options.segment_padding = round(tuning.segmentPadding);
  options.merge_gap = round(tuning.mergeGap);
  options.min_segment = round(tuning.minSegment);
  options.ref_start = round(tuning.refStart);
  options.ref_duration = round(tuning.refDuration);

  if (tuning.normalizeLoudness) {
    options.normalize_loudness = true;
    options.target_lufs = round(tuning.targetLufs);
  }
  if (tuning.denoise) options.denoise = true;
  if (tuning.outputSampleRate > 0) options.output_sample_rate = tuning.outputSampleRate;

  if (kind === "seedvc") {
    options.seed = tuning.seed;
    options.diffusion_steps = tuning.diffusionSteps;
    options.inference_cfg_rate = round(tuning.inferenceCfgRate);
    options.n_quantizers = tuning.nQuantizers;
    options.temperature = round(tuning.temperature);
    options.length_adjust = round(tuning.lengthAdjust);
    options.overlap_frame_len = tuning.overlapFrameLen;
    options.max_window = round(tuning.maxWindow);
    options.context = round(tuning.context);
    options.fade = round(tuning.fade);
    options.ref_max_len = round(tuning.refMaxLen);
  }

  return { ...options, ...parseExtra(tuning.extraJson) };
}

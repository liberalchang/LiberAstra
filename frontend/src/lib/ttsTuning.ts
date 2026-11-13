export type TtsPreset = "calm" | "natural" | "broadcast" | "excited";

export interface TtsTuning {
  advanced: boolean;
  linked: boolean;
  /** 0 = calm, 1 = excited; only used when linked is true. */
  expressiveness: number;
  speed: number;
  exaggeration: number;
  cfgWeight: number;
}

export const DEFAULT_TTS_TUNING: TtsTuning = {
  advanced: false,
  linked: false,
  expressiveness: 1 / 3,
  speed: 1,
  exaggeration: 0.5,
  cfgWeight: 0.5,
};

export function normalizeTtsTuning(raw: unknown): TtsTuning {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_TTS_TUNING };
  const data = raw as Partial<TtsTuning>;
  return {
    advanced: Boolean(data.advanced),
    linked: Boolean(data.linked),
    expressiveness: clamp(Number(data.expressiveness ?? DEFAULT_TTS_TUNING.expressiveness), 0, 1),
    speed: clamp(Number(data.speed ?? DEFAULT_TTS_TUNING.speed), 0.8, 1.2),
    exaggeration: clamp(
      Number(data.exaggeration ?? DEFAULT_TTS_TUNING.exaggeration),
      0.2,
      1,
    ),
    cfgWeight: clamp(Number(data.cfgWeight ?? DEFAULT_TTS_TUNING.cfgWeight), 0.3, 0.7),
  };
}

export const TTS_PRESETS: {
  id: TtsPreset;
  label: string;
  at: number;
  speed: number;
  exaggeration: number;
  cfgWeight: number;
}[] = [
  { id: "calm", label: "平静", at: 0, speed: 0.9, exaggeration: 0.35, cfgWeight: 0.55 },
  { id: "natural", label: "自然", at: 1 / 3, speed: 1.0, exaggeration: 0.5, cfgWeight: 0.5 },
  { id: "broadcast", label: "播报", at: 2 / 3, speed: 1.05, exaggeration: 0.65, cfgWeight: 0.45 },
  { id: "excited", label: "激动", at: 1, speed: 1.15, exaggeration: 0.9, cfgWeight: 0.35 },
];

const round = (value: number) => Math.round(value * 1000) / 1000;
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));

export function tuningAt(expressiveness: number): {
  preset: TtsPreset;
  speed: number;
  exaggeration: number;
  cfgWeight: number;
} {
  const value = clamp(expressiveness, 0, 1);
  let left = TTS_PRESETS[0];
  let right = TTS_PRESETS[TTS_PRESETS.length - 1];
  for (let index = 0; index < TTS_PRESETS.length - 1; index += 1) {
    if (value <= TTS_PRESETS[index + 1].at) {
      left = TTS_PRESETS[index];
      right = TTS_PRESETS[index + 1];
      break;
    }
  }
  const span = right.at - left.at;
  const ratio = span <= 0 ? 0 : (value - left.at) / span;
  const nearest = value - left.at <= right.at - value + 1e-9 ? left : right;
  return {
    preset: nearest.id,
    speed: round(left.speed + (right.speed - left.speed) * ratio),
    exaggeration: round(left.exaggeration + (right.exaggeration - left.exaggeration) * ratio),
    cfgWeight: round(left.cfgWeight + (right.cfgWeight - left.cfgWeight) * ratio),
  };
}

export function tuningFromPreset(preset: TtsPreset, current: TtsTuning): TtsTuning {
  const item = TTS_PRESETS.find((candidate) => candidate.id === preset) ?? TTS_PRESETS[1];
  return {
    ...current,
    linked: true,
    expressiveness: item.at,
    speed: item.speed,
    exaggeration: item.exaggeration,
    cfgWeight: item.cfgWeight,
  };
}

export function ttsOptions(
  tuning: TtsTuning,
  supportsEmotion: boolean,
): Record<string, number> {
  if (!tuning.advanced) return {};
  const values = tuning.linked && supportsEmotion
    ? tuningAt(tuning.expressiveness)
    : {
        speed: tuning.speed,
        exaggeration: tuning.exaggeration,
        cfgWeight: tuning.cfgWeight,
      };
  const options: Record<string, number> = { speed: values.speed };
  if (supportsEmotion) {
    options.exaggeration = values.exaggeration;
    options.cfg_weight = values.cfgWeight;
  }
  return options;
}

export function supportsEmotionModel(model: string | null | undefined): boolean {
  const id = (model || "").split(" · ")[0].trim().toLowerCase();
  return id !== "turbo" && id !== "nano";
}

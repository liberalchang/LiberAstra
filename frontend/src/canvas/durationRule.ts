export type DurationMode = "manual" | "audio" | "source_video" | "clips" | "source";

export interface DurationRule {
  mode: DurationMode;
  /** true 表示执行器会忽略 length/frames，不要再按 duration_limits 限制总时长。 */
  lengthIgnored: boolean;
  /** 当前规则是否给成片总时长设上限。 */
  totalLimit: boolean;
  note: string;
}

const MANUAL_NOTE =
  "length 控制单段时长；duration_limits 是单段上限，不是成片总时长上限。即使连接了参考音频，普通视频节点也不会按音频长度自动延长；需要更长时改用连续生成（clips_json）或分段拼接。";

export function durationRuleFor(
  capability: string | null | undefined,
  hasClips: boolean,
): DurationRule {
  const cap = (capability || "").toLowerCase();
  if (cap === "avatar") {
    return {
      mode: "audio",
      lengthIgnored: true,
      totalLimit: false,
      note: "成片时长跟随上游音频；length/frames 会被执行器忽略。超过单段上限会自动切片并拼接，不要要求用户压缩文案或音频。",
    };
  }
  if (cap === "motion") {
    return {
      mode: "source_video",
      lengthIgnored: true,
      totalLimit: false,
      note: "成片时长跟随参考视频；length/frames 会被执行器忽略。超过单段上限会自动切分并按参考窗口衔接，不要要求用户裁短参考视频。",
    };
  }
  if (hasClips) {
    return {
      mode: "clips",
      lengthIgnored: true,
      totalLimit: false,
      note: "用 clips_json 的 duration 控制每段时长；单段不超过模型上限，总时长可超过单段上限。",
    };
  }
  if (cap === "upscale" || cap === "v2v" || cap === "video_upscale" || cap === "analysis") {
    return {
      mode: "source",
      lengthIgnored: true,
      totalLimit: false,
      note: "时长跟随输入视频，不填 length。",
    };
  }
  return {
    mode: "manual",
    lengthIgnored: false,
    totalLimit: false,
    note: MANUAL_NOTE,
  };
}

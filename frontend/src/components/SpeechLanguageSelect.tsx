import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/api/client";
import { Field, selectClass } from "@/components/ui/field";
import { useTx } from "@/i18n/tx";

/** 与 Liber Speech 的 language_id 一致。中文、英文放在前面。 */
export const SPEECH_LANGUAGES: { code: string; label: string }[] = [
  { code: "zh", label: "中文 zh" },
  { code: "en", label: "英文 en" },
  { code: "ja", label: "日文 ja" },
  { code: "ko", label: "韩文 ko" },
  { code: "fr", label: "法文 fr" },
  { code: "de", label: "德文 de" },
  { code: "es", label: "西班牙文 es" },
  { code: "pt", label: "葡萄牙文 pt" },
  { code: "ru", label: "俄文 ru" },
  { code: "it", label: "意大利文 it" },
  { code: "ar", label: "阿拉伯文 ar" },
  { code: "hi", label: "印地文 hi" },
  { code: "tr", label: "土耳其文 tr" },
  { code: "nl", label: "荷兰文 nl" },
  { code: "pl", label: "波兰文 pl" },
  { code: "sv", label: "瑞典文 sv" },
  { code: "da", label: "丹麦文 da" },
  { code: "no", label: "挪威文 no" },
  { code: "fi", label: "芬兰文 fi" },
  { code: "el", label: "希腊文 el" },
  { code: "he", label: "希伯来文 he" },
  { code: "ms", label: "马来文 ms" },
  { code: "sw", label: "斯瓦希里文 sw" },
];

const ALL_CODES = SPEECH_LANGUAGES.map((item) => item.code);

/** 11 个 Chatterbox 模型包。功能页不选模型，只按系统默认包过滤语言。 */
export const SPEECH_MODELS: { id: string; label: string; group: string; languages: string[] }[] = [
  { id: "multilingual_v3", label: "Chatterbox-Multilingual V3", group: "multilingual", languages: ALL_CODES },
  { id: "multilingual_v2", label: "Chatterbox-Multilingual V2", group: "multilingual", languages: ALL_CODES },
  { id: "zh-cmn", label: "Chinese (zh-CMN)", group: "pack", languages: ["zh"] },
  { id: "es-mx", label: "Latam Spanish", group: "pack", languages: ["es"] },
  { id: "pt-br", label: "Brazilian Portuguese", group: "pack", languages: ["pt"] },
  { id: "es-es", label: "Spain Spanish", group: "pack", languages: ["es"] },
  { id: "pt-pt", label: "Portugal Portuguese", group: "pack", languages: ["pt"] },
  { id: "hi", label: "Hindi", group: "pack", languages: ["hi"] },
  { id: "turbo", label: "Chatterbox-Turbo", group: "english", languages: ["en"] },
  { id: "nano", label: "Chatterbox-Nano", group: "english", languages: ["en"] },
  { id: "standard", label: "Chatterbox", group: "english", languages: ["en"] },
];

export const SPEECH_MODEL_GROUPS: { id: string; label: string }[] = [
  { id: "multilingual", label: "多语言模型" },
  { id: "pack", label: "单语言精调包" },
  { id: "english", label: "英文模型" },
];

/** 系统设置里的语音转文字模型。空值跟随语音服务 .env。 */
export const SPEECH_ASR_MODELS: { id: string; label: string }[] = [
  { id: "", label: "跟随语音服务配置 (.env)" },
  { id: "large-v3", label: "faster-whisper large-v3" },
  { id: "large-v3-turbo", label: "faster-whisper large-v3-turbo" },
  { id: "qwen3-asr-1.7b", label: "Qwen3-ASR-1.7B" },
];

export function asrModelHint(model: string): string {
  if (!model) return "不选具体模型时，使用语音服务 .env 里的 LIBER_SPEECH_ASR_MODEL。";
  if (model === "qwen3-asr-1.7b") return "带时间戳，服务会收成句子字幕。不支持译成英语。";
  if (model === "large-v3-turbo") return "比 large-v3 更快。语音翻译请改用 large-v3。";
  return "99 种语言，支持转写和译成英语。";
}

export function speechModelOf(model: string) {
  return SPEECH_MODELS.find((item) => item.id === model) ?? SPEECH_MODELS[0];
}

export function languagesForModel(model: string) {
  const allowed = new Set(speechModelOf(model).languages);
  return SPEECH_LANGUAGES.filter((item) => allowed.has(item.code));
}

/** 当前模型包不支持的语言会改成该包的第一项。 */
export function speechLanguage(value: string, model = "multilingual_v3"): string {
  const langs = languagesForModel(model);
  return langs.some((item) => item.code === value) ? value : (langs[0]?.code ?? "zh");
}

export function speechModelHint(model: string): string {
  const spec = speechModelOf(model);
  if (spec.id === "turbo" || spec.id === "nano") {
    return "只读英文。克隆参考音频需要长于 5 秒。Turbo 支持 [laugh] 这类副语言标记。";
  }
  if (spec.group === "english") return "只读英文。";
  if (spec.group === "pack") return `只读 ${spec.languages[0]}。功能页的语言下拉只保留这一项。`;
  return "支持 23 种语言。功能页的语言下拉会列出全部。";
}

export const EDGE_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural";

/** 两位语言码属于 Liber Speech，不是 Edge TTS 或 OpenAI 兼容 TTS 的音色名。 */
export function isLanguageCodeVoice(value: string): boolean {
  return /^[a-z]{2}$/i.test(value.trim());
}

/** 列表里已有就保留；语言码或空值改成中文默认音色，否则用列表第一项。 */
export function edgeVoiceOrDefault(current: string, voices: string[]): string {
  if (current && voices.includes(current)) return current;
  if (current && !isLanguageCodeVoice(current) && voices.length === 0) return current;
  if (voices.includes(EDGE_DEFAULT_VOICE)) return EDGE_DEFAULT_VOICE;
  if (voices[0]) return voices[0];
  if (current && !isLanguageCodeVoice(current)) return current;
  return EDGE_DEFAULT_VOICE;
}

const SERVICE_MODEL_ID = /tts|whisper|gpt-|sensevoice|asr/i;

/** 同一份拉取结果里，模型 id 和音色名分开。全是模型 id 时不再当成音色。 */
export function partitionServiceNames(items: string[]): { voices: string[]; models: string[] } {
  if (items.length === 0) return { voices: [], models: [] };
  const models = items.filter((item) => SERVICE_MODEL_ID.test(item));
  if (models.length === items.length) return { voices: [], models: items };
  return { voices: items.filter((item) => !SERVICE_MODEL_ID.test(item)), models };
}

/** 清掉写进音色名里的语言码。Edge 回到默认音色，OpenAI 兼容回到列表或空。 */
export function sanitizeServiceVoice(
  current: string,
  voices: string[],
  kind: "edge_tts" | "openai_tts",
): string {
  if (kind === "edge_tts") return edgeVoiceOrDefault(current, voices);
  if (isLanguageCodeVoice(current) && !voices.includes(current)) return voices[0] ?? "";
  return current;
}

/** 系统设置里的默认 Liber Speech 模型包。 */
export function useDefaultSpeechModel(): string {
  const { data } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  return data?.default_speech_model || "multilingual_v3";
}

/** Liber Speech 的发音语言。列表跟随系统默认模型包。 */
export function SpeechLanguageSelect({
  value,
  onChange,
  model = "multilingual_v3",
}: {
  value: string;
  onChange: (code: string) => void;
  model?: string;
}) {
  const tx = useTx();
  const langs = languagesForModel(model);
  const selected = speechLanguage(value, model);
  useEffect(() => {
    if (selected !== value) onChange(selected);
  }, [onChange, selected, value]);
  return (
    <Field
      label={tx("语言")}
      hint={
        langs.length === 1
          ? tx("当前模型包只使用这一种语言。选用音色库时，参考音频仍然用来克隆音色。")
          : tx("按当前模型包发音。选用音色库时，这里只决定语言，参考音频仍然用来克隆音色。")
      }
    >
      <select className={selectClass} value={selected} onChange={(e) => onChange(e.target.value)}>
        {langs.map((item) => (
          <option key={item.code} value={item.code}>
            {tx(item.label)}
          </option>
        ))}
      </select>
    </Field>
  );
}

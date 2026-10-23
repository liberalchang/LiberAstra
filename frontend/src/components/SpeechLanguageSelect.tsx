import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/api/client";
import { Field, selectClass } from "@/components/ui/field";
import { useTx } from "@/i18n/tx";

/** 与 Liber Speech 的 language_id 一致。中文、英文放在前面。 */
const SPEECH_LANGUAGES: { code: string; label: string }[] = [
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
          ? tx("当前默认模型包只使用这一种语言。选用音色库时，参考音频仍然用来克隆音色。")
          : tx("按系统设置里的默认模型包发音。选用音色库时，这里只决定语言，参考音频仍然用来克隆音色。")
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

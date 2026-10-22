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

/** 识别不了的值按中文处理，和后端 language_from_voice 一致。 */
export function speechLanguage(value: string): string {
  return SPEECH_LANGUAGES.some((item) => item.code === value) ? value : "zh";
}

/** Liber Speech 不克隆音色时选择发音语言。 */
export function SpeechLanguageSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (code: string) => void;
}) {
  const tx = useTx();
  return (
    <Field
      label={tx("语言")}
      hint={tx("不使用音色库时，模型用自带的默认声音，按这个语言发音。")}
    >
      <select
        className={selectClass}
        value={speechLanguage(value)}
        onChange={(e) => onChange(e.target.value)}
      >
        {SPEECH_LANGUAGES.map((item) => (
          <option key={item.code} value={item.code}>
            {tx(item.label)}
          </option>
        ))}
      </select>
    </Field>
  );
}

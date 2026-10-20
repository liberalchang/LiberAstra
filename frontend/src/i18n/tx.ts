import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { UI_EN } from "@/i18n/ui-en";

/** 界面文案：中文为原文，英文从对照表取。未收录的句子保持中文。 */
export function useTx() {
  const { i18n } = useTranslation();
  return useCallback(
    (zh: string, vars?: Record<string, string | number>) => {
      let text = i18n.language.startsWith("en") ? (UI_EN[zh] ?? zh) : zh;
      if (vars) {
        for (const [key, value] of Object.entries(vars)) {
          text = text.replaceAll(`{${key}}`, String(value));
        }
      }
      return text;
    },
    [i18n.language],
  );
}

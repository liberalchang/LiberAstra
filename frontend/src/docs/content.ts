import { moduleKeyToSlug, type DocLocale } from "./links";

export type DocPage = {
  slug: string;
  source: string;
  locale: DocLocale;
  fallback: boolean;
};

const zhModules = import.meta.glob(
  [
    "../../../site/docs-src/*.md",
    "../../../site/docs-src/guides/*.md",
    "../../../site/docs-src/integration/*.md",
  ],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const enModules = import.meta.glob(
  [
    "../../../site/docs-src/en/*.md",
    "../../../site/docs-src/en/guides/*.md",
    "../../../site/docs-src/en/integration/*.md",
  ],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

function toMap(modules: Record<string, string>, locale: DocLocale): Map<string, string> {
  const map = new Map<string, string>();
  for (const [key, source] of Object.entries(modules)) {
    map.set(moduleKeyToSlug(key, locale), source);
  }
  return map;
}

const ZH = toMap(zhModules, "zh");
const EN = toMap(enModules, "en");

export function getDoc(locale: DocLocale, slug: string): DocPage | null {
  const key = slug || "index";
  if (locale === "en") {
    const translated = EN.get(key);
    if (translated) return { slug: key, source: translated, locale: "en", fallback: false };
    const original = ZH.get(key);
    if (original) return { slug: key, source: original, locale: "zh", fallback: true };
    return null;
  }
  const source = ZH.get(key);
  return source ? { slug: key, source, locale: "zh", fallback: false } : null;
}

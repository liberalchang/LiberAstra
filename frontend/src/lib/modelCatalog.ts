/** 从 Provider.extra 读取模型目录。SettingsPage、功能页和画布菜单调用。 */

import type { ModelItem, ProviderOut } from "@/api/client";

const CATEGORIES = new Set(["llm", "image", "video", "tts", "asr", "unknown"]);

export function readCatalog(extra: ProviderOut["extra"] | undefined): ModelItem[] {
  const raw = extra?.model_catalog;
  if (!Array.isArray(raw)) return [];
  const items: ModelItem[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const row = entry as Record<string, unknown>;
    const id = String(row.id ?? "").trim();
    if (!id) continue;
    const category = String(row.category ?? "unknown");
    items.push({
      id,
      label: String(row.label ?? id),
      category: CATEGORIES.has(category) ? category : "unknown",
      sub_capabilities: Array.isArray(row.sub_capabilities)
        ? row.sub_capabilities.map((item) => String(item))
        : [],
      enabled: Boolean(row.enabled),
      custom: Boolean(row.custom),
      params: readParams(row.params),
    });
  }
  return items;
}

function readParams(raw: unknown): ModelItem["params"] | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const row = raw as Record<string, unknown>;
  const params: NonNullable<ModelItem["params"]> = {};
  if (typeof row.max_output === "number" && row.max_output >= 1) {
    params.max_output = row.max_output;
  }
  if (row.defaults && typeof row.defaults === "object") {
    const defaults: Record<string, string | number | boolean> = {};
    for (const [key, value] of Object.entries(row.defaults as Record<string, unknown>)) {
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        defaults[key] = value;
      }
    }
    if (Object.keys(defaults).length > 0) params.defaults = defaults;
  }
  return params.max_output || params.defaults ? params : undefined;
}

export function enabledModels(provider: ProviderOut | undefined, subCapability: string): ModelItem[] {
  if (!provider) return [];
  return readCatalog(provider.extra).filter(
    (item) => item.enabled && item.sub_capabilities.includes(subCapability),
  );
}

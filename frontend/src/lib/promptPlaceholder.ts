import type { WorkflowInputSpec } from "@/api/client";

/** 空提示词框的灰字：优先用工作流包里「提示词」字段的 description。 */
type Tx = (zh: string, vars?: Record<string, string | number>) => string;

type PackLike = {
  capability?: string;
  inputs?: Record<string, WorkflowInputSpec>;
} | null | undefined;

const MAX_PLACEHOLDER = 80;

const CAPABILITY_FALLBACK: Record<string, string> = {
  t2i: "描述要生成的画面",
  i2i: "说明要怎么改",
  upscale: "可选，用来约束画面",
  i2v: "描述镜头、运动和声音",
  t2v: "描述镜头、运动和声音",
  motion: "描述镜头、运动和声音",
  avatar: "描述镜头、运动和声音",
};

export const CANVAS_PROMPT_HINT = "输入简短描述…键入 / 可引用已连接节点的变量";

function fieldDescription(inputs: Record<string, WorkflowInputSpec> | undefined, key: string): string {
  const raw = inputs?.[key]?.description?.replace(/\s+/g, " ").trim() ?? "";
  if (raw.length <= MAX_PLACEHOLDER) return raw;
  const cut = raw.slice(0, MAX_PLACEHOLDER);
  const stop = Math.max(cut.lastIndexOf("。"), cut.lastIndexOf("；"));
  return (stop >= 20 ? cut.slice(0, stop + 1) : cut).trim();
}

/** 页面灰字用包说明；画布把「键入 /」留在前面，包说明接在后面。 */
export function workflowPromptPlaceholder(
  tx: Tx,
  pack: PackLike,
  options?: { canvas?: boolean; fallback?: string },
): string {
  const desc = fieldDescription(pack?.inputs, "prompt");
  if (options?.canvas) {
    const prefix = tx(CANVAS_PROMPT_HINT);
    return desc ? `${prefix}。${tx(desc)}` : prefix;
  }
  if (desc) return tx(desc);
  const fallback = options?.fallback || CAPABILITY_FALLBACK[pack?.capability || ""] || "输入简短描述…";
  return tx(fallback);
}

export function negativePromptPlaceholder(tx: Tx, pack: PackLike): string {
  const desc = fieldDescription(pack?.inputs, "negative_prompt");
  return tx(desc || "不希望出现的内容，可以留空。");
}

/** 多张参考图的上传说明：按槽位名称，不套用某一类包的合影句子。 */
export function referenceImagesHint(tx: Tx, slots: [string, WorkflowInputSpec][]): string {
  const labels = slots.map(([, spec], index) => spec.label?.trim() || tx("图{n}", { n: index + 1 }));
  if (labels.length === 2) {
    return tx("按顺序添加：第 1 张是{a}，第 2 张是{b}。", { a: tx(labels[0]), b: tx(labels[1]) });
  }
  const list = labels
    .map((name, index) => tx("第 {n} 张是{name}", { n: index + 1, name: tx(name) }))
    .join("，");
  return tx("按顺序添加：{list}。", { list });
}

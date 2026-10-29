/** 与后端 clean_appearance 对齐：去掉定妆照排版句，只留能写进分镜的外观。 */

const LAYOUT_MARKERS = [
  "16:9",
  "横版角色设定",
  "画面依次展示",
  "画面从左到右",
  "四个视角",
  "完整全身正面",
  "右侧超大面部",
  "右侧特写",
  "不裁脚",
  "浅灰纯色",
  "影棚背景",
  "空白间隔",
  "不要伸进",
  "Lookbook",
  "8K",
  "写实真人质感",
  "柔和棚拍光",
];

const LAYOUT_PHRASES = [
  "角色三视图设定",
  "三视图设定",
  "四段式角色设定图",
  "四段式定妆照",
  "角色定妆照",
];

export const CHARACTER_VIEWS = [
  ["turnaround", "定妆照"],
  ["portrait", "面部特写"],
  ["front", "正面全身"],
  ["side", "侧面全身"],
  ["back", "背面全身"],
] as const;

export type CharacterView = (typeof CHARACTER_VIEWS)[number][0];

export function cleanAppearance(text: string): string {
  const kept: string[] = [];
  for (const chunk of text.split(/[。\n]/)) {
    let piece = chunk.trim().replace(/^[ ，,;；]+|[ ，,;；]+$/g, "");
    if (!piece || LAYOUT_MARKERS.some((marker) => piece.includes(marker))) continue;
    for (const phrase of LAYOUT_PHRASES) piece = piece.replaceAll(phrase, "");
    piece = piece.trim().replace(/^[ ，,;；]+|[ ，,;；]+$/g, "");
    if (piece) kept.push(piece);
  }
  return kept.join("。");
}

export function viewLabel(view: string): string {
  return CHARACTER_VIEWS.find(([key]) => key === view)?.[1] ?? "正面全身";
}

/** 交给提示词优化的角色上下文。motion 单角色时补上三张全身图的 Picture 对应关系。 */
export function characterPromptContext(
  name: string,
  description: string,
  view: string,
  motion = false,
): string {
  const detail = cleanAppearance(description);
  const base = `登场角色：${name}。固定外观：${detail}。当前参考图视角：${viewLabel(view)}`;
  if (view === "turnaround") return `${base}。参考图是整张四段式定妆照。`;
  if (!motion) return `${base}。`;
  return `${base}。<Picture 1> 是正面，<Picture 2> 是侧面，<Picture 3> 是背面，都是同一个人。`;
}

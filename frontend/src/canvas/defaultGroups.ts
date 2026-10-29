/** 「按能力建默认分组」的共用逻辑:NodeInspector 首用引导与 QuickAddMenu 空态共用。
 * 按包 capability 归到 图像/视频/语音/画面分析;一个包都没有时返回 null。
 */
import { api, type WorkflowPackOut } from "@/api/client";

const GROUP_CAPS: [string, string[]][] = [
  ["图像", ["t2i", "i2i", "upscale"]],
  ["视频", ["t2v", "i2v", "avatar", "motion"]],
  ["语音", ["tts", "asr"]],
  ["画面分析", ["analysis"]],
];

export async function createDefaultGroups(
  packs: WorkflowPackOut[],
): Promise<Record<string, string[]> | null> {
  const groups: Record<string, string[]> = {};
  for (const [name, caps] of GROUP_CAPS) {
    const names = packs.filter((p) => caps.includes(p.capability)).map((p) => p.name);
    if (names.length) groups[name] = names;
  }
  if (Object.keys(groups).length === 0) return null;
  await api.putCanvasGroups(groups);
  return groups;
}

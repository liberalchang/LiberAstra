/**
 * 提示词槽位规范化器：纯确定性规则/正则，不调用 LLM。
 * 明确序号 → image_N；模糊指代不猜测；越界拒绝；保护普通数字。
 */

export type NormalizeSlotsParams = {
  prompt: string;
  actualImageCount: number;
  imageRoles?: string[];
  /** 默认 `image_{n}` */
  slotTemplate?: string;
};

export type NormalizeSlotsResult = {
  originalPrompt: string;
  normalizedPrompt: string;
  referencedSlots: number[];
  warnings: string[];
};

const CN_DIGITS: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
};

function parseChineseNumber(token: string): number | null {
  const t = token.trim();
  if (!t) return null;
  if (/^\d+$/.test(t)) return Number(t);
  if (t === "十") return 10;
  if (t.length === 1 && t in CN_DIGITS) return CN_DIGITS[t];
  const m1 = t.match(/^十([一二三四五六七八九])?$/);
  if (m1) return 10 + (m1[1] ? CN_DIGITS[m1[1]] : 0);
  const m2 = t.match(/^([二三四五六七八九])十([一二三四五六七八九])?$/);
  if (m2) return CN_DIGITS[m2[1]] * 10 + (m2[2] ? CN_DIGITS[m2[2]] : 0);
  return null;
}

function ordinalWordToNumber(word: string): number | null {
  const map: Record<string, number> = {
    first: 1,
    second: 2,
    third: 3,
    fourth: 4,
    fifth: 5,
    sixth: 6,
    seventh: 7,
    eighth: 8,
    ninth: 9,
    tenth: 10,
    eleventh: 11,
    twelfth: 12,
    thirteenth: 13,
    fourteenth: 14,
    fifteenth: 15,
    sixteenth: 16,
    seventeenth: 17,
    eighteenth: 18,
    nineteenth: 19,
    twentieth: 20,
  };
  return map[word.toLowerCase()] ?? null;
}

function formatSlot(n: number, template: string): string {
  return template.replace("{n}", String(n)).replace("{N}", String(n));
}

/** 保护：尺寸、比例、步数、CFG、普通数量词等 */
const PROTECT_PATTERNS: RegExp[] = [
  /\b\d{3,5}\s*[x×]\s*\d{3,5}\b/gi,
  /\b\d{3,5}\s*(?:px|宽|高|宽度|高度)\b/gi,
  /\b(?:CFG|cfg)\s*[:=]?\s*\d+(?:\.\d+)?\b/g,
  /\b\d+\s*(?:步|steps?)\b/gi,
  /\b\d+\s*:\s*\d+\b/g,
  /[一二两三四五六七八九十百]+(?:个|只|位|人|名|条|天|小时|分钟|秒)/g,
  /第[一二两三四五六七八九十百\d]+\s*张\s*(?:桌子|椅子|床|纸|票)/g,
  /\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:people|persons|cats|dogs|men|women)\b/gi,
];

const FUZZY_HINT =
  /左边那张|右边那张|上面那张|下面那张|中间那张|衣服那张|背景那张|那张图|那张照片|\bthe\s+left\s+(?:one|image)\b|\bthe\s+right\s+(?:one|image)\b/gi;

type MatchHit = {
  start: number;
  end: number;
  slot: number;
};

function applyProtect(prompt: string): { masked: string; rawByToken: Map<string, string> } {
  const hits: { start: number; end: number; text: string }[] = [];
  for (const re of PROTECT_PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(prompt)) !== null) {
      hits.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
    }
  }
  hits.sort((a, b) => a.start - b.start);
  const merged: typeof hits = [];
  for (const h of hits) {
    const last = merged[merged.length - 1];
    if (last && h.start < last.end) continue;
    merged.push(h);
  }
  const rawByToken = new Map<string, string>();
  let masked = prompt;
  for (let i = merged.length - 1; i >= 0; i -= 1) {
    const h = merged[i];
    const token = `__OCP_PROTECT_${i}__`;
    rawByToken.set(token, h.text);
    masked = masked.slice(0, h.start) + token + masked.slice(h.end);
  }
  return { masked, rawByToken };
}

function collectExplicitHits(masked: string): MatchHit[] {
  const hits: MatchHit[] = [];
  const push = (start: number, end: number, slot: number) => {
    hits.push({ start, end, slot });
  };

  let m: RegExpExecArray | null;
  const reImageToken = /(?:<image\s*(\d+)\s*>|\bimage[_\s-]?(\d+)\b)/gi;
  while ((m = reImageToken.exec(masked)) !== null) {
    const n = Number(m[1] ?? m[2]);
    if (Number.isFinite(n)) push(m.index, m.index + m[0].length, n);
  }

  const reCnPrefix = /(?:参考)?(?:图|图片|照片|图像)\s*([0-9一二两三四五六七八九十百]+)/g;
  while ((m = reCnPrefix.exec(masked)) !== null) {
    const n = parseChineseNumber(m[1]);
    if (n != null) push(m.index, m.index + m[0].length, n);
  }

  // 必须带图片语义后置词，避免「第一张桌子」；后置词保持短匹配以免吞句
  const reOrdinalCn =
    /第\s*([0-9一二两三四五六七八九十百]+)\s*张\s*(?:参考)?(?:图|图片|照片|图像|人物|人像|主体|角色|衣服|服装|背景|姿态|姿势)/g;
  while ((m = reOrdinalCn.exec(masked)) !== null) {
    const n = parseChineseNumber(m[1]);
    if (n == null) continue;
    push(m.index, m.index + m[0].length, n);
  }

  const reEnOrd =
    /\b(?:(\d+)(?:st|nd|rd|th)|(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth))\s+(?:reference\s+)?(?:image|photo|picture)s?\b/gi;
  while ((m = reEnOrd.exec(masked)) !== null) {
    let n: number | null = null;
    if (m[1]) n = Number(m[1]);
    else if (m[2]) n = ordinalWordToNumber(m[2]);
    if (n != null) push(m.index, m.index + m[0].length, n);
  }

  hits.sort((a, b) => a.start - b.start || b.end - a.end);
  const filtered: MatchHit[] = [];
  let cursor = -1;
  for (const h of hits) {
    if (h.start < cursor) continue;
    filtered.push(h);
    cursor = h.end;
  }
  return filtered;
}

/**
 * 规范化提示词中的明确图片指代。
 * @throws 越界序号或无图却含明确序号
 */
export function normalizePromptSlots(params: NormalizeSlotsParams): NormalizeSlotsResult {
  const originalPrompt = params.prompt ?? "";
  const actualImageCount = params.actualImageCount;
  const template = params.slotTemplate ?? "image_{n}";
  const warnings: string[] = [];

  let working = originalPrompt;
  if (params.imageRoles?.length) {
    // 长角色名优先，避免短名误伤；中文角色按子串替换（调用方显式提供，非猜测）
    const roleEntries = params.imageRoles
      .map((role, i) => ({ role: role?.trim() ?? "", index: i + 1 }))
      .filter((e) => e.role)
      .sort((a, b) => b.role.length - a.role.length);
    for (const entry of roleEntries) {
      if (!working.includes(entry.role)) continue;
      const slot = formatSlot(entry.index, template);
      working = working.split(entry.role).join(slot);
      warnings.push(`角色映射: "${entry.role}" → ${slot}`);
    }
  }

  FUZZY_HINT.lastIndex = 0;
  if (FUZZY_HINT.test(working)) {
    warnings.push(
      "检测到模糊图片指代（如「左边那张」「衣服那张」），未做猜测；请改用明确序号或提供 imageRoles",
    );
  }

  const { masked, rawByToken } = applyProtect(working);
  const explicitHits = collectExplicitHits(masked);
  const referencedSlots = [...new Set(explicitHits.map((h) => h.slot))].sort((a, b) => a - b);

  if (actualImageCount === 0 && referencedSlots.length > 0) {
    throw Object.assign(
      new Error(
        `无参考图模式下提示词含明确图片序号（${referencedSlots
          .map((n) => formatSlot(n, template))
          .join(", ")}），拒绝静默退回文生图`,
      ),
      { code: "VALIDATION_FAILED" as const },
    );
  }

  const oob = referencedSlots.filter((n) => n < 1 || n > actualImageCount);
  if (oob.length > 0) {
    throw Object.assign(
      new Error(
        `提示词引用了不存在的图片槽位：${oob
          .map((n) => formatSlot(n, template))
          .join(", ")}（实际仅 ${actualImageCount} 张）`,
      ),
      {
        code: "VALIDATION_FAILED" as const,
        details: { missingSlots: oob, actualImageCount },
      },
    );
  }

  let normalizedMasked = masked;
  for (const h of [...explicitHits].sort((a, b) => b.start - a.start)) {
    const replacement = formatSlot(h.slot, template);
    normalizedMasked =
      normalizedMasked.slice(0, h.start) + replacement + normalizedMasked.slice(h.end);
  }

  let normalizedPrompt = normalizedMasked;
  for (const [token, text] of rawByToken) {
    normalizedPrompt = normalizedPrompt.split(token).join(text);
  }

  return {
    originalPrompt,
    normalizedPrompt,
    referencedSlots,
    warnings,
  };
}

export const __testables = {
  parseChineseNumber,
  formatSlot,
  applyProtect,
  collectExplicitHits,
};

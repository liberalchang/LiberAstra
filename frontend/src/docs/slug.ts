import GithubSlugger from "github-slugger";

export type DocHeading = { level: number; text: string; id: string };

/** 去掉文首的 YAML frontmatter；正文前的空行一并清理。 */
export function stripFrontmatter(source: string): string {
  return source.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n\s*/, "");
}

/** 标题的纯文本：去掉行内代码、链接、强调符号，供 slug 和目录使用。 */
export function plainHeadingText(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/[*~]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** 按文档顺序生成与 rehype-slug 一致的 id（重复标题自动加 -1、-2）。 */
export function extractHeadings(source: string): DocHeading[] {
  const slugger = new GithubSlugger();
  const headings: DocHeading[] = [];
  let inFence = false;

  for (const line of stripFrontmatter(source).split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;

    const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (!match) continue;
    const text = plainHeadingText(match[2]);
    headings.push({ level: match[1].length, text, id: slugger.slug(text) });
  }
  return headings;
}

export function tocHeadings(source: string): DocHeading[] {
  return extractHeadings(source).filter(
    (heading) => heading.level === 2 || heading.level === 3,
  );
}

import type { ReactNode } from "react";

/** 只覆盖使用文档里用到的 Markdown：标题、段落、列表、表格、代码。 */
export function MarkdownView({ source }: { source: string }) {
  return <article className="guide-doc flex flex-col gap-3 text-sm leading-6 text-foreground">{renderBlocks(source)}</article>;
}

function renderBlocks(source: string): ReactNode[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(
        <pre key={key++} className="overflow-x-auto rounded-xl bg-muted px-4 py-3 text-[13px]">
          <code>{body.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i]
          .split("|")
          .slice(1, -1)
          .map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-+:?$/.test(cell))) rows.push(cells);
        i += 1;
      }
      const [head, ...body] = rows;
      blocks.push(
        <div key={key++} className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full border-collapse text-left text-sm">
            {head && (
              <thead className="bg-muted/70">
                <tr>
                  {head.map((cell, index) => (
                    <th key={index} className="px-3 py-2 font-medium">
                      {inline(cell, `h${index}`)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {body.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t border-border">
                  {row.map((cell, index) => (
                    <td key={index} className="px-3 py-2 align-top">
                      {inline(cell, `c${rowIndex}-${index}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    // 水平分割线（文档里的 ---），跳过即可
    if (/^---+$/.test(line.trim())) {
      i += 1;
      continue;
    }
    if (/^[-*] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(lines[i].slice(2));
        i += 1;
      }
      blocks.push(
        <ul key={key++} className="list-disc space-y-1 pl-5">
          {items.map((item, index) => (
            <li key={index}>{inline(item, `li${index}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^\d+\. /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ""));
        i += 1;
      }
      blocks.push(
        <ol key={key++} className="list-decimal space-y-1 pl-5">
          {items.map((item, index) => (
            <li key={index}>{inline(item, `ol${index}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    // 支持 #～######；原先只认到 ###，遇到 #### 时既不前进也不渲染 → 死循环卡死 /guide
    const heading = /^(#{1,6}) (.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      const className =
        level === 1
          ? "text-2xl font-semibold tracking-tight"
          : level === 2
            ? "mt-4 text-lg font-semibold"
            : level === 3
              ? "mt-2 text-base font-semibold"
              : "mt-1 text-sm font-semibold text-foreground/90";
      const Tag = level <= 2 ? (level === 1 ? "h2" : "h3") : level === 3 ? "h4" : "h5";
      blocks.push(
        <Tag key={key++} className={className}>
          {inline(text, "hx")}
        </Tag>,
      );
      i += 1;
      continue;
    }
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^---+$/.test(lines[i].trim()) &&
      !lines[i].startsWith("#") &&
      !lines[i].startsWith("|") &&
      !lines[i].startsWith("```") &&
      !/^[-*] /.test(lines[i]) &&
      !/^\d+\. /.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    // 防御：无法归类的行也必须前进，避免死循环
    if (para.length === 0) {
      i += 1;
      continue;
    }
    blocks.push(
      <p key={key++} className="text-foreground/90">
        {inline(para.join(" "), "p")}
      </p>,
    );
  }
  return blocks;
}

function inline(text: string, prefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;
  while ((match = re.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      parts.push(
        <code key={`${prefix}-${index++}`} className="rounded bg-muted px-1 py-0.5 text-[13px]">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      parts.push(
        <strong key={`${prefix}-${index++}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>,
      );
    }
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

import assert from "node:assert/strict";
import { test } from "node:test";

import { docPath, moduleKeyToSlug, resolveDocHref, slugFromPath } from "./links.ts";
import { extractHeadings, stripFrontmatter, tocHeadings } from "./slug.ts";

test("stripFrontmatter removes the YAML block only", () => {
  const source = "---\ntitle: 图像\n---\n\n# 图像\n\n正文";
  assert.equal(stripFrontmatter(source), "# 图像\n\n正文");
  assert.equal(stripFrontmatter("# 标题\n\n正文"), "# 标题\n\n正文");
});

test("extractHeadings skips fenced code and matches rehype-slug ids", () => {
  const source = [
    "---",
    "title: 图像",
    "---",
    "# 图像",
    "## 文生图",
    "### 文生图：`flux3_klein`",
    "```",
    "## not a heading",
    "```",
    "### 文生图：`flux3_klein`",
    "## 文生图",
  ].join("\n");

  assert.deepEqual(
    extractHeadings(source).map((heading) => [heading.level, heading.id]),
    [
      [1, "图像"],
      [2, "文生图"],
      [3, "文生图flux3_klein"],
      [3, "文生图flux3_klein-1"],
      [2, "文生图-1"],
    ],
  );
});

test("tocHeadings keeps H2 and H3 only", () => {
  const source = "# 图像\n\n## 文生图\n\n### 子节\n\n#### 更深";
  assert.deepEqual(
    tocHeadings(source).map((heading) => heading.level),
    [2, 3],
  );
});

test("resolveDocHref maps VitePress paths into the unified docs route", () => {
  assert.deepEqual(resolveDocHref("/guides/image", "zh"), {
    href: "/guide/guides/image",
    external: false,
  });
  assert.deepEqual(resolveDocHref("/en/guides/image#qwen", "en"), {
    href: "/guide/guides/image#qwen",
    external: false,
  });
  assert.deepEqual(resolveDocHref("/", "zh"), { href: "/guide", external: false });
  assert.deepEqual(resolveDocHref("/en/", "en"), { href: "/guide", external: false });
  assert.deepEqual(resolveDocHref("#文字转语音", "zh"), {
    href: "#文字转语音",
    external: false,
  });
  assert.deepEqual(resolveDocHref("https://example.com", "zh"), {
    href: "https://example.com",
    external: true,
  });
  assert.deepEqual(resolveDocHref("/docs", "zh"), { href: "/docs", external: true });
  assert.deepEqual(resolveDocHref("./installation.md", "zh"), {
    href: "/guide/installation",
    external: false,
  });
});

test("docPath and slugFromPath preserve the default route", () => {
  assert.equal(docPath("index"), "/guide");
  assert.equal(docPath("guides/image"), "/guide/guides/image");
  assert.equal(slugFromPath(""), "index");
  assert.equal(slugFromPath("guides/image"), "guides/image");
});

test("moduleKeyToSlug strips the repo prefix and language folder", () => {
  assert.equal(
    moduleKeyToSlug("../../../site/docs-src/guides/image.md", "zh"),
    "guides/image",
  );
  assert.equal(
    moduleKeyToSlug("../../../site/docs-src/en/guides/image.md", "en"),
    "guides/image",
  );
});

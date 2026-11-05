"""检查 site/docs-src 中英文文档是否一一对应。

用法：python scripts/check_docs_parity.py
退出码：0 全部通过；1 有缺页或标题层级数量不一致。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "site" / "docs-src"
EN = DOCS / "en"


def markdown_files(base: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.md", "guides/*.md", "integration/*.md"):
        files.extend(sorted(base.glob(pattern)))
    return files


def headings(path: Path) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            result.append((len(match.group(1)), match.group(2).strip()))
    return result


def count_levels(items: list[tuple[int, str]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for level, _ in items:
        counts[level] = counts.get(level, 0) + 1
    return counts


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for zh_path in markdown_files(DOCS):
        relative = zh_path.relative_to(DOCS)
        en_path = EN / relative
        if not en_path.exists():
            errors.append(f"缺少英文页：en/{relative.as_posix()}")
            continue

        zh_headings = headings(zh_path)
        en_headings = headings(en_path)
        zh_counts = count_levels(zh_headings)
        en_counts = count_levels(en_headings)
        for level in (1, 2, 3):
            if zh_counts.get(level, 0) != en_counts.get(level, 0):
                errors.append(
                    f"{relative.as_posix()}: H{level} 数量不一致 "
                    f"zh={zh_counts.get(level, 0)} en={en_counts.get(level, 0)}"
                )

        zh_lines = len(zh_path.read_text(encoding="utf-8").splitlines())
        en_lines = len(en_path.read_text(encoding="utf-8").splitlines())
        if en_lines < zh_lines * 0.5:
            warnings.append(
                f"{relative.as_posix()}: 英文页明显偏短 zh={zh_lines} en={en_lines}"
            )

    nav_path = DOCS / "nav.json"
    nav = json.loads(nav_path.read_text(encoding="utf-8"))
    for locale in ("zh", "en"):
        base = DOCS if locale == "zh" else EN
        for section in nav[locale]["sections"]:
            for item in section["items"]:
                slug = item["slug"]
                target = base / (f"{slug}.md" if slug != "index" else "index.md")
                if not target.exists():
                    errors.append(f"nav.json {locale} 条目不存在：{slug}")

    for warning in warnings:
        print(f"警告：{warning}")
    for error in errors:
        print(f"错误：{error}")
    if errors:
        print(f"\n失败：{len(errors)} 个问题")
        return 1
    print(f"通过：{len(markdown_files(DOCS))} 个中文页均有对应英文页，标题层级一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import { BookOpen, ChevronRight } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useParams } from "react-router-dom";

import { DocsMarkdown } from "@/docs/DocsMarkdown";
import { getDoc } from "@/docs/content";
import { docPath, slugFromPath, type DocLocale } from "@/docs/links";
import { docSections, docTitle, type DocNavSection } from "@/docs/manifest";
import { tocHeadings, type DocHeading } from "@/docs/slug";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";

export function GuidePage() {
  const { i18n } = useTranslation();
  const tx = useTx();
  const params = useParams();
  const location = useLocation();
  const locale: DocLocale = i18n.language.startsWith("en") ? "en" : "zh";
  const slug = slugFromPath(params["*"] ?? "");
  const doc = getDoc(locale, slug);
  const sections = docSections(locale);
  const title = doc ? docTitle(locale, slug) : tx("文档不存在");

  const docSource = doc?.source ?? "";
  const toc = useMemo(() => tocHeadings(docSource), [docSource]);

  useEffect(() => {
    const id = location.hash ? decodeURIComponent(location.hash.slice(1)) : "";
    const target = id ? document.getElementById(id) : null;
    if (target) {
      requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
      return;
    }
    document.querySelector<HTMLElement>("main")?.scrollTo({ top: 0 });
  }, [slug, location.hash, doc?.locale]);

  if (!doc) {
    return (
      <div className="mx-auto flex max-w-xl flex-col items-start gap-3 rounded-2xl border border-border bg-card p-6">
        <h1 className="text-xl font-semibold">{tx("文档不存在")}</h1>
        <p className="text-sm text-muted-foreground">
          {tx("没有找到这个章节，可能链接已经过期。")}
        </p>
        <Link
          to="/guide"
          className="text-sm font-medium text-primary underline underline-offset-2"
        >
          {tx("返回文档首页")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <BookOpen className="size-4" />
        <Link to="/guide" className="transition-colors hover:text-foreground">
          {tx("使用文档")}
        </Link>
        <ChevronRight className="size-3.5" />
        <span className="text-foreground">{title}</span>
      </div>

      {doc.fallback && (
        <div className="rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          {tx("此页暂无英文翻译，显示中文原文。")}
        </div>
      )}

      <details className="rounded-2xl border border-border bg-card px-4 py-3 lg:hidden">
        <summary className="cursor-pointer text-sm font-medium">{tx("文档目录")}</summary>
        <div className="mt-3">
          <DocSidebar sections={sections} activeSlug={slug} />
        </div>
      </details>

      <div className="grid gap-8 lg:grid-cols-[210px_minmax(0,1fr)] xl:grid-cols-[210px_minmax(0,1fr)_200px]">
        <aside className="hidden lg:block">
          <div className="sticky top-4 max-h-[calc(100vh-9rem)] overflow-y-auto pr-2">
            <DocSidebar sections={sections} activeSlug={slug} />
          </div>
        </aside>

        <article className="min-w-0 rounded-2xl border border-border bg-card p-5 md:p-7">
          <DocsMarkdown source={doc.source} locale={doc.locale} />
        </article>

        <aside className="hidden xl:block">
          <DocToc headings={toc} label={tx("本页目录")} />
        </aside>
      </div>
    </div>
  );
}

function DocSidebar({
  sections,
  activeSlug,
}: {
  sections: DocNavSection[];
  activeSlug: string;
}) {
  return (
    <nav className="space-y-5 text-sm" aria-label="doc-sections">
      {sections.map((section) => (
        <div key={section.title}>
          <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {section.title}
          </p>
          <ul className="space-y-0.5">
            {section.items.map((item) => (
              <li key={item.slug}>
                <Link
                  to={docPath(item.slug)}
                  className={cn(
                    "block rounded-lg px-2 py-1.5 transition-colors",
                    item.slug === activeSlug
                      ? "bg-primary/10 font-medium text-primary"
                      : "text-foreground/75 hover:bg-muted hover:text-foreground",
                  )}
                >
                  {item.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function DocToc({ headings, label }: { headings: DocHeading[]; label: string }) {
  if (headings.length === 0) return null;
  return (
    <nav
      className="sticky top-4 max-h-[calc(100vh-9rem)] overflow-y-auto pr-1 text-sm"
      aria-label="table-of-contents"
    >
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <ul className="space-y-0.5 border-l border-border">
        {headings.map((heading) => (
          <li key={heading.id} className={heading.level === 3 ? "pl-3" : "pl-1.5"}>
            <a
              href={`#${heading.id}`}
              className="block rounded-r py-0.5 pl-2 text-muted-foreground transition-colors hover:text-foreground"
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

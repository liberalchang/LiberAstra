export type DocLocale = "zh" | "en";

const DOCS_PREFIX = "../../../site/docs-src/";

export function moduleKeyToSlug(key: string, locale: DocLocale): string {
  let slug = key.startsWith(DOCS_PREFIX) ? key.slice(DOCS_PREFIX.length) : key;
  slug = slug.replace(/\.md$/, "");
  if (locale === "en") slug = slug.replace(/^en\//, "");
  return slug;
}

export function docPath(slug: string): string {
  return slug === "index" ? "/guide" : `/guide/${slug}`;
}

export function slugFromPath(path: string): string {
  const slug = path.replace(/^\/+|\/+$/g, "");
  return slug || "index";
}

export type DocLink = { href: string; external: boolean };

export function resolveDocHref(raw: string, _locale: DocLocale): DocLink {
  const href = raw.trim();
  if (/^(https?:|mailto:|tel:)/i.test(href)) return { href, external: true };
  if (href.startsWith("#")) return { href, external: false };

  if (href.startsWith("/")) {
    // /docs 是后端 Swagger，不是文档章节
    if (href === "/docs" || href.startsWith("/docs/")) return { href, external: true };
    if (href === "/en" || href === "/en/") return { href: "/guide", external: false };

    const path = href.startsWith("/en/") ? href.slice(3) : href;
    const [base, hash] = path.split("#");
    const slug = base.replace(/^\/+|\/+$/g, "");
    if (!slug) return { href: "/guide", external: false };
    return { href: `/guide/${slug}${hash ? `#${hash}` : ""}`, external: false };
  }

  const [base, hash] = href.split("#");
  if (base.endsWith(".md")) {
    const slug = base.replace(/^\.\//, "").replace(/\.md$/, "");
    return { href: `/guide/${slug}${hash ? `#${hash}` : ""}`, external: false };
  }
  return { href, external: false };
}

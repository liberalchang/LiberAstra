import nav from "../../../site/docs-src/nav.json";

import type { DocLocale } from "./links";

export type DocNavItem = { title: string; slug: string };
export type DocNavSection = { title: string; items: DocNavItem[] };

const NAV = nav as Record<DocLocale, { sections: DocNavSection[] }>;

export function docSections(locale: DocLocale): DocNavSection[] {
  return NAV[locale].sections;
}

export function docTitle(locale: DocLocale, slug: string): string {
  for (const section of docSections(locale)) {
    const item = section.items.find((entry) => entry.slug === slug);
    if (item) return item.title;
  }
  return slug;
}

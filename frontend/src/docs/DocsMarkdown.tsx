import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import { remarkHeadingIds } from "@/docs/headingIds";
import { resolveDocHref, type DocLocale } from "@/docs/links";
import { stripFrontmatter } from "@/docs/slug";

export function DocsMarkdown({ source, locale }: { source: string; locale: DocLocale }) {
  return (
    <div className="docs-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkHeadingIds]}
        rehypePlugins={[rehypeSlug]}
        components={{
          a: ({ href, children }) => {
            const link = resolveDocHref(href ?? "", locale);
            if (link.external) {
              return (
                <a href={link.href} target="_blank" rel="noreferrer">
                  {children}
                </a>
              );
            }
            if (link.href.startsWith("#")) {
              return <a href={link.href}>{children}</a>;
            }
            return <Link to={link.href}>{children}</Link>;
          },
          table: ({ children }) => (
            <div className="docs-table">
              <table>{children}</table>
            </div>
          ),
          img: ({ src, alt }) => (
            <img src={src ?? ""} alt={alt ?? ""} loading="lazy" />
          ),
        }}
      >
        {stripFrontmatter(source)}
      </ReactMarkdown>
    </div>
  );
}

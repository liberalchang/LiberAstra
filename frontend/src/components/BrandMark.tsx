import { cn } from "@/lib/utils";

/** 品牌星标：主星 + 伴星 + 远星，对应 Astra（星辰）与编排平台的双星意象；favicon.svg 使用同一组路径。 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
      fill="none"
      className={cn("block", className)}
    >
      <path
        d="M27 8c1.8 13.2 5.8 17.2 19 19-13.2 1.8-17.2 5.8-19 19-1.8-13.2-5.8-17.2-19-19 13.2-1.8 17.2-5.8 19-19Z"
        fill="currentColor"
      />
      <path
        d="M47 37c.9 6.6 2.9 8.6 9.5 9.5-6.6.9-8.6 2.9-9.5 9.5-.9-6.6-2.9-8.6-9.5-9.5 6.6-.9 8.6-2.9 9.5-9.5Z"
        fill="currentColor"
        opacity=".85"
      />
      <circle cx="47" cy="18" r="2.4" fill="currentColor" opacity=".7" />
    </svg>
  );
}

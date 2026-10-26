import { cloneElement, isValidElement, useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** 表单字段：可见标签、控件、一行说明。标签与控件程序化关联（屏幕阅读器可读）。 */
export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  const autoId = useId();
  // 控件是唯一子元素时注入 id，让 <label htmlFor> 真正指向它；组合控件保持原样
  const control = isValidElement(children)
    ? cloneElement(children as React.ReactElement<{ id?: string; "aria-describedby"?: string }>, {
        id: (children.props as { id?: string }).id ?? autoId,
      })
    : children;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={autoId} className="text-sm font-medium text-foreground">
        {label}
      </label>
      {control}
      {hint ? <span className="text-xs leading-relaxed text-muted-foreground">{hint}</span> : null}
    </div>
  );
}

/** 下拉框：隐藏原生箭头，用统一的 chevron 背景图（明暗主题通用灰）。 */
const CHEVRON_BG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`;

export const selectClass = cn(
  "h-11 w-full appearance-none rounded-[10px] border border-border bg-field px-3 pr-9 text-sm text-foreground",
  "bg-no-repeat bg-[right_0.75rem_center] bg-[length:16px]",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  `bg-[image:var(--select-chevron)]`,
);

export const areaClass =
  "w-full rounded-[10px] border border-border bg-field p-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export { CHEVRON_BG };

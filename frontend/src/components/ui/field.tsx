import { cloneElement, isValidElement, useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** 表单字段：可见标签、控件、一行说明。标签与控件程序化关联（屏幕阅读器可读）。 */
export function Field({
  label,
  hint,
  className,
  children,
  trailing,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
  trailing?: ReactNode;
}) {
  const autoId = useId();
  const isElement = isValidElement(children);
  const canClone =
    isElement && (typeof children.type === "string" || typeof children.type === "function");
  const isNativeControl =
    canClone &&
    typeof children.type === "string" &&
    ["input", "select", "textarea"].includes(children.type);
  const childProps = isElement
    ? (children.props as { id?: string; "aria-label"?: string })
    : ({} as { id?: string; "aria-label"?: string });
  const controlId = childProps.id ?? autoId;
  // 原生控件用 label htmlFor 关联；自定义组件可能有自己的 aria-label，
  // 不生成指向不存在 id 的 for，避免浏览器 a11y 警告。
  const control = canClone
    ? cloneElement(
        children as React.ReactElement<{ id?: string; "aria-label"?: string }>,
        isNativeControl
          ? { id: controlId }
          : { "aria-label": childProps["aria-label"] ?? label },
      )
    : children;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      {isNativeControl ? (
        <label htmlFor={controlId} className="text-sm font-medium text-foreground">
          {label}
        </label>
      ) : (
        <span className="text-sm font-medium text-foreground">{label}</span>
      )}
      {trailing ? (
        <div className="relative min-w-0">
          {control}
          <div className="absolute inset-y-0 right-0.5 flex items-center">{trailing}</div>
        </div>
      ) : (
        control
      )}
      {hint ? <span className="text-xs leading-relaxed text-muted-foreground">{hint}</span> : null}
    </div>
  );
}

/** 下拉框：隐藏原生箭头，用统一的 chevron 背景图（明暗主题通用灰）。 */
const CHEVRON_BG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`;

export const selectClass = cn(
  "h-11 w-full appearance-none rounded-[10px] border border-border bg-field px-3 pr-9 text-sm text-foreground shadow-[inset_0_1px_0_var(--edge-highlight)]",
  "bg-no-repeat bg-[right_0.75rem_center] bg-[length:16px]",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  `bg-[image:var(--select-chevron)]`,
);

export const areaClass =
  "w-full rounded-[10px] border border-border bg-field p-3 text-sm text-foreground shadow-[inset_0_1px_0_var(--edge-highlight)] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export { CHEVRON_BG };

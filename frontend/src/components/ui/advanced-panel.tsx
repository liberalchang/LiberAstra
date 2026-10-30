import type { ReactNode } from "react";

import { useTx } from "@/i18n/tx";

/** 把专家参数收进默认收起的折叠区，摘要留在标题上。 */
export function AdvancedPanel({ summary, children }: { summary: string; children: ReactNode }) {
  const tx = useTx();
  return (
    <details className="rounded-xl border border-border bg-muted/40">
      <summary className="cursor-pointer list-none px-3 py-2.5 text-sm [&::-webkit-details-marker]:hidden">
        <span className="font-medium">{tx("高级参数")}</span>
        {summary && <span className="ml-2 text-muted-foreground">{summary}</span>}
      </summary>
      <div className="flex flex-col gap-4 border-t border-border px-3 py-3">{children}</div>
    </details>
  );
}

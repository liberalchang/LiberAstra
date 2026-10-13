import { BookOpen } from "lucide-react";

import { MarkdownView } from "@/components/MarkdownView";
import { PageHeader } from "@/components/PageShell";
import guide from "../../../docs/使用文档.md?raw";

export function GuidePage() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader
        kind="guide"
        icon={BookOpen}
        title="使用文档"
        description="当前只写了已经测通的文生图。其它能力测通后再补进同一份文档。"
      />
      <MarkdownView source={guide} />
    </div>
  );
}

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
        description="出图、放大和语音的用法。视频页还对不上这台机器上的权重。"
      />
      <MarkdownView source={guide} />
    </div>
  );
}

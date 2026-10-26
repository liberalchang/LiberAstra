import { BookOpen } from "lucide-react";

import { MarkdownView } from "@/components/MarkdownView";
import { PageHeader } from "@/components/PageShell";
import guide from "../../../docs/使用文档.md?raw";
import { useTx } from "@/i18n/tx";

export function GuidePage() {
  const tx = useTx();
  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader
        kind="guide"
        icon={BookOpen}
        title={tx("使用文档")}
        description={tx("按侧栏功能说明用法；视频与 Comfy 工作流见「服务提供方 → 工作流包 → 模型文件」。")}
      />
      <MarkdownView source={guide} />
    </div>
  );
}

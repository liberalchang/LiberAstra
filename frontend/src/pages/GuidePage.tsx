import { BookOpen } from "lucide-react";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useTx } from "@/i18n/tx";

/** 旧 /guide 路由跳到 VitePress 站点 /manual/，保留子路径与 hash。 */
export function GuidePage() {
  const tx = useTx();
  const location = useLocation();

  useEffect(() => {
    const rest = location.pathname.replace(/^\/guide\/?/, "");
    const target = rest ? `/manual/${rest}${location.hash}` : `/manual/${location.hash}`;
    window.location.replace(target);
  }, [location.pathname, location.hash]);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-start gap-3 rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <BookOpen className="size-4" />
        <span>{tx("使用文档")}</span>
      </div>
      <p className="text-sm text-muted-foreground">{tx("正在打开使用文档…")}</p>
    </div>
  );
}

/** 画布顶部的功能面板。平时只留一个入口，点开后按大类铺开，点功能即收起并建节点。
 * CanvasPage 放在 top-center。数据来自 /api/v1/canvases/menu。
 */

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@xyflow/react";
import { ImageIcon, Mic, Search, Video, X } from "lucide-react";
import { useMemo, useState } from "react";

import { api, type CanvasMenuItem } from "@/api/client";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  ["speech", "语音", Mic],
  ["image", "图像", ImageIcon],
  ["video", "视频", Video],
] as const;

const RECENT_KEY = "canvas-menu-recent";

function readRecent(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function remember(id: string) {
  const next = [id, ...readRecent().filter((item) => item !== id)].slice(0, 6);
  localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}

export function CanvasFunctionMenu({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (item: CanvasMenuItem) => void;
}) {
  const tx = useTx();
  const [query, setQuery] = useState("");
  const [recentIds, setRecentIds] = useState<string[]>(() => readRecent());
  const { data: menu } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const needle = query.trim().toLowerCase();
  const items = useMemo(
    () =>
      (menu ?? []).filter(
        (item) => item.enabled !== false && (!needle || `${item.title} ${item.hint}`.toLowerCase().includes(needle)),
      ),
    [menu, needle],
  );
  const recent = recentIds
    .map((id) => (menu ?? []).find((item) => item.id === id && item.enabled !== false))
    .filter((item): item is CanvasMenuItem => Boolean(item))
    .filter((item) => !needle || `${item.title} ${item.hint}`.toLowerCase().includes(needle));

  const choose = (item: CanvasMenuItem) => {
    remember(item.id);
    setRecentIds(readRecent());
    setQuery("");
    onOpenChange(false);
    onPick(item);
  };

  if (!open) {
    return (
      <Panel position="top-center" className="mt-14">
        <button
          type="button"
          className="rounded-full border border-border bg-card/95 px-4 py-1.5 text-sm shadow-md hover:bg-muted"
          onClick={() => onOpenChange(true)}
        >
          {tx("全部功能")}
        </button>
      </Panel>
    );
  }

  return (
    <Panel position="top-center" className="mt-14">
      <div className="w-[min(52rem,88vw)] rounded-2xl border border-border bg-card/95 p-4 shadow-xl">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="shrink-0 text-sm font-medium">{tx("全部功能")}</h2>
          <label className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              placeholder={tx("搜索功能")}
              className="h-8 w-full rounded-lg border border-border bg-background pl-8 pr-2 text-sm outline-none"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button type="button" className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label={tx("关闭")} onClick={() => onOpenChange(false)}>
            <X className="size-4" />
          </button>
        </div>
        {recent.length > 0 && (
          <section className="mb-4">
            <h3 className="mb-2 text-xs text-muted-foreground">{tx("最近使用")}</h3>
            <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
              {recent.map((item) => (
                <FunctionButton key={`recent-${item.id}`} item={item} onClick={() => choose(item)} />
              ))}
            </div>
          </section>
        )}
        {CATEGORIES.map(([category, label, Icon]) => {
          const rows = items.filter((item) => item.category === category);
          if (rows.length === 0) return null;
          return (
            <section key={category} className="mb-4 last:mb-0">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Icon className="size-3.5" />
                {tx(label)}
              </h3>
              <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
                {rows.map((item) => (
                  <FunctionButton key={item.id} item={item} onClick={() => choose(item)} />
                ))}
              </div>
            </section>
          );
        })}
        {items.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">{tx("没有匹配的功能")}</p>}
      </div>
    </Panel>
  );
}

function FunctionButton({ item, onClick }: { item: CanvasMenuItem; onClick: () => void }) {
  return (
    <button
      type="button"
      title={item.hint}
      className={cn("truncate rounded-lg px-2 py-2 text-left text-sm hover:bg-muted")}
      onClick={onClick}
    >
      {item.title}
    </button>
  );
}

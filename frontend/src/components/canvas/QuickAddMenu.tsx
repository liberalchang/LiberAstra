/** 添加节点。一级是输入、合成和功能大类，二级向右展开。
 * CanvasPage 在底部 +、节点 + 和拖线落空时打开。
 */

import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Mic,
  UsersRound,
  Video,
} from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { api, type CanvasMenuItem } from "@/api/client";
import type { CanvasNodeKind, MediaKind, SpeechMode } from "@/canvas/types";
import { useTx } from "@/i18n/tx";

export interface QuickAddPick {
  kind: CanvasNodeKind;
  mediaKind?: MediaKind;
  group?: string;
  speechMode?: SpeechMode;
  menu?: CanvasMenuItem;
}

const IO_ITEMS: { kind: CanvasNodeKind; mediaKind?: MediaKind; icon: typeof ImageIcon; label: string }[] = [
  { kind: "input", mediaKind: "image", icon: ImageIcon, label: "图片输入" },
  { kind: "input", mediaKind: "character", icon: UsersRound, label: "角色输入" },
  { kind: "input", mediaKind: "video", icon: Video, label: "视频输入" },
  { kind: "input", mediaKind: "audio", icon: AudioLines, label: "音频输入" },
  { kind: "input", mediaKind: "text", icon: FileText, label: "文本输入" },
  { kind: "concat", mediaKind: "video", icon: Clapperboard, label: "视频合成" },
  { kind: "concat", mediaKind: "audio", icon: AudioLines, label: "音频合成" },
];

const GROUPS = [
  ["input", "输入", FolderOpen],
  ["concat", "合成", Clapperboard],
  ["speech", "语音", Mic],
  ["image", "图像", ImageIcon],
  ["video", "视频", Video],
] as const;

export function QuickAddMenu({
  x,
  y,
  onPick,
  onClose,
}: {
  /** 屏幕坐标（相对画布容器） */
  x: number;
  y: number;
  onPick: (pick: QuickAddPick) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const menuRef = useRef<HTMLDivElement>(null);
  const [openGroup, setOpenGroup] = useState<string | null>("input");
  const [side, setSide] = useState<"right" | "left">("right");
  const [flyoutMax, setFlyoutMax] = useState(320);
  const { data: menu } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const functions = (menu ?? []).filter((item) => item.enabled !== false);

  useLayoutEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const parent = el.offsetParent instanceof HTMLElement ? el.offsetParent.getBoundingClientRect() : null;
    const limit = parent?.right ?? window.innerWidth;
    const floor = parent?.bottom ?? window.innerHeight;
    // 只有右侧放不下整块二级菜单时才改向左，避免贴边时被画布裁掉。
    setSide(rect.right + 232 > limit - 8 ? "left" : "right");
    setFlyoutMax(Math.max(160, floor - rect.top - 12));
  }, []);

  useEffect(() => {
    const prevFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    menuRef.current?.querySelector<HTMLElement>("[data-group]")?.focus();
    return () => prevFocus?.focus();
  }, []);

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      return;
    }
    const root = menuRef.current;
    const flyout = root?.querySelector<HTMLElement>('[data-menu="flyout"]');
    const inFlyout = Boolean(flyout?.contains(document.activeElement));
    if (e.key === "ArrowRight" && !inFlyout) {
      const group = (document.activeElement as HTMLElement | null)?.dataset.group;
      if (!group) return;
      e.preventDefault();
      setOpenGroup(group);
      requestAnimationFrame(() => {
        root?.querySelector<HTMLElement>('[data-menu="flyout"] button')?.focus();
      });
      return;
    }
    if (e.key === "ArrowLeft" && inFlyout) {
      e.preventDefault();
      root?.querySelector<HTMLElement>(`[data-group="${openGroup}"]`)?.focus();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Tab") return;
    const scope = inFlyout ? flyout : root?.querySelector<HTMLElement>('[data-menu="primary"]');
    const items = Array.from(scope?.querySelectorAll<HTMLElement>("button") ?? []);
    if (items.length === 0) return;
    e.preventDefault();
    const backwards = e.key === "ArrowUp" || (e.key === "Tab" && e.shiftKey);
    const current = items.indexOf(document.activeElement as HTMLElement);
    const next = backwards
      ? (current - 1 + items.length) % items.length
      : (current + 1) % items.length;
    items[next]?.focus();
  };

  const itemClass = "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted";
  const Chevron = side === "right" ? ChevronRight : ChevronLeft;

  const flyout = (() => {
    if (openGroup === "input" || openGroup === "concat") {
      return IO_ITEMS.filter((item) => item.kind === openGroup).map((item) => (
        <button
          key={`${item.kind}-${item.mediaKind}`}
          type="button"
          className={itemClass}
          onClick={() => onPick({ kind: item.kind, mediaKind: item.mediaKind })}
        >
          <item.icon className="size-3.5 text-primary/70" />
          {tx(item.label)}
        </button>
      ));
    }
    if (!openGroup) return null;
    const rows = functions.filter((item) => item.category === openGroup);
    if (rows.length === 0) {
      return <p className="px-2 py-1.5 text-xs text-muted-foreground">{tx("这一类还没有功能")}</p>;
    }
    return rows.map((item) => (
      <button
        key={item.id}
        type="button"
        title={item.hint}
        className={itemClass}
        onClick={() =>
          onPick({
            kind: item.category === "speech" ? "speech" : "function",
            speechMode: item.sub_capability === "asr" ? "asr" : undefined,
            menu: item,
          })
        }
      >
        {item.title}
      </button>
    ));
  })();

  return (
    <>
      <button type="button" className="fixed inset-0 z-30 cursor-default" aria-label={tx("关闭")} onClick={onClose} />
      <div
        ref={menuRef}
        className="absolute z-40 w-44 rounded-xl border border-border bg-card p-1.5 shadow-lg"
        style={{ left: x, top: y }}
        role="menu"
        onKeyDown={onMenuKeyDown}
      >
        <div data-menu="primary" className="flex flex-col">
          {GROUPS.map(([id, label, Icon]) => {
            const open = openGroup === id;
            return (
              <button
                key={id}
                type="button"
                data-group={id}
                className={`${itemClass} ${open ? "bg-muted" : ""}`}
                aria-expanded={open}
                aria-haspopup="menu"
                onMouseEnter={() => setOpenGroup(id)}
                onFocus={() => setOpenGroup(id)}
                onClick={() => setOpenGroup(id)}
              >
                {side === "left" && <Chevron className="size-3.5 text-muted-foreground" />}
                <Icon className="size-3.5 text-primary/70" />
                <span className="flex-1">{tx(label)}</span>
                {side === "right" && <Chevron className="size-3.5 text-muted-foreground" />}
              </button>
            );
          })}
        </div>
        {openGroup && (
          <div
            data-menu="flyout"
            role="menu"
            className={`absolute top-0 z-10 w-56 ${side === "right" ? "left-full -ml-1 pl-2" : "right-full -mr-1 pr-2"}`}
          >
            <div
              className="overflow-y-auto rounded-xl border border-border bg-card p-1.5 shadow-lg"
              style={{ maxHeight: flyoutMax }}
            >
              {flyout}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

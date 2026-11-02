import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { NavIcon } from "@/nav/icons";
import type { NavGroupEntry } from "@/nav/model";
import { cn } from "@/lib/utils";
import { NavLeafLink } from "./NavLeafLink";

const FLYOUT_WIDTH = 288;
const VIEWPORT_MARGIN = 12;

export function NavFlyout({
  group,
  anchor,
  onClose,
  onNavigate,
}: {
  group: NavGroupEntry;
  anchor: HTMLElement | null;
  onClose: () => void;
  onNavigate?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!anchor || !panel) return;
    const rect = anchor.getBoundingClientRect();
    const sidebar = anchor.closest("aside");
    const sidebarRect = sidebar?.getBoundingClientRect();
    const height = panel.offsetHeight;
    let left = (sidebarRect?.right ?? rect.right) + 8;
    let top = rect.top - 6;

    if (left + FLYOUT_WIDTH > window.innerWidth - VIEWPORT_MARGIN) {
      left = Math.max(VIEWPORT_MARGIN, (sidebarRect?.left ?? rect.left) - FLYOUT_WIDTH - 8);
    }
    if (height > 0) {
      if (top + height > window.innerHeight - VIEWPORT_MARGIN) {
        top = window.innerHeight - height - VIEWPORT_MARGIN;
      }
      if (top < VIEWPORT_MARGIN) top = VIEWPORT_MARGIN;
    }

    setPosition({ top, left });
  }, [anchor, group.id, i18n.language]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (panelRef.current?.contains(target) || anchor?.contains(target)) return;
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      const hadFocus =
        panelRef.current?.contains(document.activeElement) || document.activeElement === anchor;
      onClose();
      if (hadFocus) anchor?.focus();
    };
    const handleResize = () => onClose();
    const handleScroll = (event: Event) => {
      if (panelRef.current?.contains(event.target as Node)) return;
      onClose();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResize);
    window.addEventListener("scroll", handleScroll, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [anchor, onClose]);

  const handlePanelKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const panel = panelRef.current;
    if (!panel) return;
    const links = Array.from(panel.querySelectorAll<HTMLElement>("a[href]"));
    if (links.length === 0) return;
    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const index = active ? links.indexOf(active) : -1;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        links[index === -1 ? 0 : (index + 1) % links.length]?.focus();
        break;
      case "ArrowUp":
        event.preventDefault();
        links[index === -1 ? links.length - 1 : (index - 1 + links.length) % links.length]?.focus();
        break;
      case "Home":
        event.preventDefault();
        links[0]?.focus();
        break;
      case "End":
        event.preventDefault();
        links[links.length - 1]?.focus();
        break;
      case "ArrowLeft":
        event.preventDefault();
        onClose();
        anchor?.focus();
        break;
      default:
        break;
    }
  };

  const activate = () => {
    onNavigate?.();
    onClose();
  };

  return (
    <div
      ref={panelRef}
      id={`nav-panel-${group.id}`}
      role="group"
      aria-label={t(group.labelKey)}
      onKeyDown={handlePanelKeyDown}
      style={{
        top: position?.top ?? 0,
        left: position?.left ?? 0,
        width: FLYOUT_WIDTH,
        maxHeight: "calc(100vh - 24px)",
      }}
      className={cn(
        "nav-scroll fixed z-40 overflow-y-auto rounded-2xl border border-border bg-card shadow-lg",
        !position && "invisible",
      )}
    >
      <div className="sticky top-0 z-10 flex h-9 items-center gap-2 border-b border-border bg-card px-3 text-xs font-medium text-muted-foreground">
        <NavIcon name={group.icon} className="size-3.5 shrink-0" />
        <span className="truncate">{t(group.labelKey)}</span>
      </div>
      <div className="p-1.5">
        {group.sections.map((section, sectionIndex) => (
          <div key={section.labelKey ?? sectionIndex}>
            {section.labelKey ? (
              <div
                className={cn(
                  "px-2.5 pb-1 pt-2 text-[11px] font-medium text-muted-foreground",
                  sectionIndex > 0 && "mt-1 border-t border-border",
                )}
              >
                {t(section.labelKey)}
              </div>
            ) : null}
            <ul className="flex flex-col gap-0.5">
              {section.items.map((leaf) => (
                <li key={leaf.href ?? leaf.to}>
                  <NavLeafLink leaf={leaf} onActivate={activate} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

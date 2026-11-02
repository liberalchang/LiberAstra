import { useCallback, useEffect, useRef, useState, type FocusEvent as ReactFocusEvent } from "react";
import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation } from "react-router-dom";

import { NavIcon } from "@/nav/icons";
import {
  NAV_ENTRIES,
  activeGroupId,
  isEntryActive,
  type NavEntry,
  type NavGroupEntry,
} from "@/nav/model";
import { cn } from "@/lib/utils";
import { NavFlyout } from "./NavFlyout";
import { NavLeafLink } from "./NavLeafLink";
import { navIconWellClass, navRowClass } from "./navStyles";

type NavDirectEntry = Extract<NavEntry, { kind: "link" }>;

export function SidebarNav({
  mini = false,
  mobile = false,
  onNavigate,
}: {
  mini?: boolean;
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  const activeId = activeGroupId(location.pathname);
  const [openId, setOpenId] = useState<string | null>(() => (mobile ? activeId : null));
  const buttons = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    if (!mobile) setOpenId(null);
  }, [location.pathname, mini, mobile]);

  useEffect(() => {
    if (mobile) setOpenId(activeId);
  }, [mobile, activeId]);

  const closeFlyout = useCallback(() => setOpenId(null), []);
  const setButtonRef = useCallback((id: string, node: HTMLButtonElement | null) => {
    if (node) buttons.current.set(id, node);
    else buttons.current.delete(id);
  }, []);

  const openAndFocus = useCallback((id: string) => {
    setOpenId(id);
    requestAnimationFrame(() => {
      const panel = document.getElementById(`nav-panel-${id}`);
      panel?.querySelector<HTMLElement>("a[href]")?.focus();
    });
  }, []);

  const handleBlur = (event: ReactFocusEvent<HTMLDivElement>) => {
    if (mobile) return;
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setOpenId(null);
    }
  };

  const renderDirect = (entry: NavDirectEntry) => (
    <NavLink
      to={entry.to}
      end={entry.end}
      className={({ isActive }) => navRowClass({ active: isActive, direct: true, mini })}
      title={mini ? t(entry.labelKey) : undefined}
      onClick={() => onNavigate?.()}
    >
      {({ isActive }) => (
        <>
          <span className={navIconWellClass(isActive)}>
            <NavIcon name={entry.icon} className="size-4" />
          </span>
          {!mini && <span className="flex-1 truncate">{t(entry.labelKey)}</span>}
          {!mini && isActive && (
            <span className="size-1.5 shrink-0 rounded-full bg-primary ring-2 ring-primary/15" aria-hidden />
          )}
        </>
      )}
    </NavLink>
  );

  const renderGroup = (entry: NavGroupEntry) => {
    const active = isEntryActive(location.pathname, entry);
    const open = openId === entry.id;

    return (
      <div className="flex flex-col" onBlur={handleBlur}>
        <button
          ref={(node) => setButtonRef(entry.id, node)}
          type="button"
          className={navRowClass({ active, open, mini })}
          aria-expanded={open}
          aria-controls={open ? `nav-panel-${entry.id}` : undefined}
          title={mini ? t(entry.labelKey) : undefined}
          onClick={() => setOpenId((current) => (current === entry.id ? null : entry.id))}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowDown") {
              event.preventDefault();
              openAndFocus(entry.id);
            } else if (event.key === "ArrowLeft" && open) {
              event.preventDefault();
              setOpenId(null);
            } else if (event.key === "Escape" && open && mobile) {
              event.preventDefault();
              setOpenId(null);
            }
          }}
        >
          <span className={navIconWellClass(active)}>
            <NavIcon name={entry.icon} className="size-4" />
          </span>
          {!mini && <span className="flex-1 truncate text-left">{t(entry.labelKey)}</span>}
          {!mini && active && (
            <span className="size-1.5 shrink-0 rounded-full bg-primary ring-2 ring-primary/15" aria-hidden />
          )}
          {!mini && (
            <ChevronRight
              aria-hidden
              className={cn(
                "size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none",
                open && "rotate-90",
              )}
            />
          )}
        </button>

        {open && !mobile && (
          <NavFlyout
            key={entry.id}
            group={entry}
            anchor={buttons.current.get(entry.id) ?? null}
            onClose={closeFlyout}
            onNavigate={onNavigate}
          />
        )}

        {open && mobile && (
          <div
            id={`nav-panel-${entry.id}`}
            role="group"
            aria-label={t(entry.labelKey)}
            className="mt-0.5 flex flex-col gap-1 pb-1 pl-3"
            onKeyDown={(event) => {
              if (event.key !== "Escape") return;
              event.preventDefault();
              setOpenId(null);
              buttons.current.get(entry.id)?.focus();
            }}
          >
            {entry.sections.map((section, sectionIndex) => (
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
                      <NavLeafLink leaf={leaf} onActivate={() => onNavigate?.()} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <nav
      aria-label={t("common.mainNav")}
      className={cn(
        "nav-scroll flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pb-4",
        mini ? "px-2" : "px-3",
      )}
    >
      {NAV_ENTRIES.map((entry) => (
        <div key={entry.id} className="flex flex-col">
          {entry.dividerBefore && (
            <div
              className={cn(
                "my-1 h-px bg-gradient-to-r from-transparent via-border to-transparent",
                mini ? "mx-auto w-6" : "mx-3",
              )}
              aria-hidden
            />
          )}
          {entry.kind === "link" ? renderDirect(entry) : renderGroup(entry)}
        </div>
      ))}
    </nav>
  );
}

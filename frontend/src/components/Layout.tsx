import { Languages, LogOut, Menu, Moon, PanelLeftClose, PanelLeftOpen, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

export function Layout() {
  const { t, i18n } = useTranslation();
  const token = useAuthStore((s) => s.token);
  const signOut = useAuthStore((s) => s.signOut);
  const [dark, setDark] = useState(() => localStorage.getItem("liberastra-theme") !== "light");
  const [banner, setBanner] = useState(() => sessionStorage.getItem("liberastra-banner") !== "off");
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("liberastra-sidebar") === "collapsed",
  );

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("liberastra-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    localStorage.setItem("liberastra-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  if (!token) return <Navigate to="/auth" replace />;

  const renderSidebar = (mini: boolean, mobile = false) => (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200",
        mini ? "w-16" : "w-60",
      )}
    >
      <div className={cn("flex items-center gap-2.5 px-4 py-4", mini && "justify-center px-2")}>
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
          <BrandMark className="size-5" />
        </span>
        {!mini && <span className="text-[15px] font-semibold tracking-tight">LiberAstra</span>}
      </div>
      <SidebarNav mini={mini} mobile={mobile} onNavigate={() => setOpen(false)} />
      <div
        className={cn(
          "flex items-center gap-1 border-t border-border px-3 py-2",
          mini && "flex-col items-center px-2",
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={() => i18n.changeLanguage(i18n.language.startsWith("zh") ? "en" : "zh")}
          title={t("common.language")}
          aria-label={t("common.language")}
        >
          <Languages />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setDark((v) => !v)}
          title={t("common.theme")}
          aria-label={t("common.theme")}
        >
          {dark ? <Sun /> : <Moon />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={signOut}
          title={t("common.logout")}
          aria-label={t("common.logout")}
        >
          <LogOut />
        </Button>
        {!mobile && (
          <Button
            variant="ghost"
            size="icon"
            className={mini ? "" : "ml-auto"}
            onClick={() => setCollapsed((v) => !v)}
            title={mini ? t("common.expand") : t("common.collapse")}
            aria-label={mini ? t("common.expand") : t("common.collapse")}
          >
            {mini ? <PanelLeftOpen /> : <PanelLeftClose />}
          </Button>
        )}
      </div>
    </aside>
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background text-foreground">
      {banner && (
        <div className="relative flex h-12 shrink-0 items-center justify-center gap-3 bg-accent px-10 text-center text-sm text-white shadow-[0_2px_10px_rgb(225_29_72/0.35)]">
          <span>{t("shell.banner")}</span>
          <button
            type="button"
            className="absolute right-3 grid size-8 place-items-center rounded-full text-white/80 hover:bg-white/15"
            aria-label={t("common.close")}
            title={t("common.close")}
            onClick={() => {
              sessionStorage.setItem("liberastra-banner", "off");
              setBanner(false);
            }}
          >
            <X className="size-4" />
          </button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <div className="hidden md:block">{renderSidebar(collapsed)}</div>
        {open && (
          <div className="fixed inset-0 z-40 md:hidden">
            <button className="absolute inset-0 bg-black/60" aria-label={t("common.close")} onClick={() => setOpen(false)} />
            <div className="relative z-10 h-full">{renderSidebar(false, true)}</div>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2 md:hidden">
            <Button variant="ghost" size="icon" onClick={() => setOpen(true)} aria-label={t("common.expand")}>
              <Menu />
            </Button>
            <span className="text-sm font-semibold">LiberAstra</span>
          </div>
          <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

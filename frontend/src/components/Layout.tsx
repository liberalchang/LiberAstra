import {
  AudioLines,
  BookOpen,
  Clapperboard,
  Code2,
  Film,
  FolderOpen,
  ImagePlus,
  ImageUp,
  Images,
  Languages,
  Terminal,
  LayoutDashboard,
  LayoutTemplate,
  Library,
  ListTodo,
  LogOut,
  Menu,
  Mic,
  Moon,
  Music,
  PanelLeftClose,
  PanelLeftOpen,
  PersonStanding,
  PlugZap,
  Settings,
  Sun,
  UserRound,
  WandSparkles,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

const NAV_GROUPS: {
  labelKey: string;
  items: { to: string; icon: typeof LayoutDashboard; key: string; href?: string; end?: boolean }[];
}[] = [
  {
    labelKey: "group.workbench",
    items: [
      { to: "/dashboard", icon: LayoutDashboard, key: "nav.dashboard" },
      { to: "/guide", icon: BookOpen, key: "nav.guide" },
    ],
  },
  {
    labelKey: "group.image",
    items: [
      { to: "/image/generate", icon: ImagePlus, key: "nav.imageGen" },
      { to: "/image/edit", icon: WandSparkles, key: "nav.imageEdit" },
      { to: "/image/upscale", icon: ImageUp, key: "nav.upscale" },
    ],
  },
  {
    labelKey: "group.video",
    items: [
      { to: "/video/quick", icon: Clapperboard, key: "nav.videoQuick" },
      { to: "/video/assets", icon: Images, key: "nav.videoAssets" },
      { to: "/video/avatar", icon: UserRound, key: "nav.avatar" },
      { to: "/video/i2v", icon: Film, key: "nav.i2v" },
      { to: "/video/motion", icon: PersonStanding, key: "nav.motion" },
      { to: "/video/characters", icon: UserRound, key: "nav.characters" },
      { to: "/video/templates", icon: LayoutTemplate, key: "nav.templates" },
    ],
  },
  {
    labelKey: "group.speech",
    items: [
      { to: "/speech/tts", icon: AudioLines, key: "nav.tts" },
      { to: "/speech/asr", icon: Mic, key: "nav.asr" },
      { to: "/speech/voices", icon: Library, key: "nav.voices" },
      { to: "/speech/music", icon: Music, key: "nav.music" },
    ],
  },
  { labelKey: "group.assets", items: [{ to: "/assets", icon: FolderOpen, key: "nav.assetList" }] },
  { labelKey: "group.jobs", items: [{ to: "/jobs", icon: ListTodo, key: "nav.jobList" }] },
  {
    labelKey: "group.settings",
    items: [
      // end：只在正好是 /settings 时高亮，避免 /settings/system 等子页把它一起点亮
      { to: "/settings", icon: PlugZap, key: "nav.providers", end: true },
      { to: "/settings/workflows", icon: Workflow, key: "nav.workflows" },
      { to: "/settings/system", icon: Settings, key: "nav.system" },
    ],
  },
  {
    labelKey: "group.developer",
    items: [
      { to: "/dev", icon: Code2, key: "nav.apiDocs", href: "/docs" },
      { to: "/dev/cli", icon: Terminal, key: "nav.cliDocs" },
    ],
  },
];

function navClass(isActive: boolean, collapsed: boolean) {
  return cn(
    "flex h-10 items-center gap-2.5 rounded-lg px-3 text-sm text-foreground/80 hover:bg-foreground/6",
    // 当前项用主色淡底 + 主色文字：颜色承担「你在哪里」的导航职责
    isActive && "bg-primary/10 font-medium text-primary hover:bg-primary/12",
    collapsed && "justify-center px-0",
  );
}

export function Layout() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
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

  const renderSidebar = (mini: boolean) => (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200",
        mini ? "w-16" : "w-60",
      )}
    >
      <div className={cn("flex items-center gap-2.5 px-4 py-4", mini && "justify-center px-2")}>
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
          L
        </span>
        {!mini && <span className="text-[15px] font-semibold tracking-tight">LiberAstra</span>}
      </div>
      <nav className={cn("nav-scroll flex flex-1 flex-col gap-4 overflow-y-auto pb-4", mini ? "px-2" : "px-3")}>
        {NAV_GROUPS.map((group) => (
          <div key={group.labelKey}>
            {mini ? (
              <div className="mx-auto mb-1 h-px w-6 bg-border" aria-hidden />
            ) : (
              <div className="px-3 pb-1 text-xs text-muted-foreground">{t(group.labelKey)}</div>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) =>
                item.href ? (
                  <a
                    key={item.to}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className={navClass(false, mini)}
                    title={mini ? t(item.key) : undefined}
                    onClick={() => setOpen(false)}
                  >
                    <item.icon className="size-4 shrink-0" />
                    {!mini && t(item.key)}
                  </a>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => navClass(isActive, mini)}
                    title={mini ? t(item.key) : undefined}
                    onClick={() => setOpen(false)}
                  >
                    <item.icon className="size-4 shrink-0" />
                    {!mini && t(item.key)}
                  </NavLink>
                ),
              )}
            </div>
          </div>
        ))}
      </nav>
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
          onClick={() => navigate("/settings/system")}
          title={t("common.settings")}
          aria-label={t("common.settings")}
        >
          <Settings />
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
            aria-label={t("common.cancel")}
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
            <button className="absolute inset-0 bg-black/60" aria-label={t("common.cancel")} onClick={() => setOpen(false)} />
            <div className="relative z-10 h-full">{renderSidebar(false)}</div>
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

import {
  AudioLines,
  Clapperboard,
  Code2,
  FolderOpen,
  Image,
  Languages,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Moon,
  Settings,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

const NAV_GROUPS: {
  labelKey: string;
  items: { to: string; icon: typeof LayoutDashboard; key: string; href?: string }[];
}[] = [
  { labelKey: "group.workbench", items: [{ to: "/dashboard", icon: LayoutDashboard, key: "nav.dashboard" }] },
  {
    labelKey: "group.speech",
    items: [
      { to: "/speech/tts", icon: AudioLines, key: "nav.tts" },
      { to: "/speech/asr", icon: AudioLines, key: "nav.asr" },
      { to: "/speech/voices", icon: AudioLines, key: "nav.voices" },
    ],
  },
  {
    labelKey: "group.image",
    items: [
      { to: "/image/generate", icon: Image, key: "nav.imageGen" },
      { to: "/image/edit", icon: Image, key: "nav.imageEdit" },
      { to: "/image/upscale", icon: Image, key: "nav.upscale" },
    ],
  },
  {
    labelKey: "group.video",
    items: [
      { to: "/video/quick", icon: Clapperboard, key: "nav.videoQuick" },
      { to: "/video/assets", icon: Clapperboard, key: "nav.videoAssets" },
      { to: "/video/avatar", icon: Clapperboard, key: "nav.avatar" },
      { to: "/video/i2v", icon: Clapperboard, key: "nav.i2v" },
      { to: "/video/motion", icon: Clapperboard, key: "nav.motion" },
    ],
  },
  { labelKey: "group.assets", items: [{ to: "/assets", icon: FolderOpen, key: "nav.assetList" }] },
  { labelKey: "group.jobs", items: [{ to: "/jobs", icon: ListChecks, key: "nav.jobList" }] },
  {
    labelKey: "group.settings",
    items: [
      { to: "/settings", icon: Settings, key: "nav.providers" },
      { to: "/settings/workflows", icon: Settings, key: "nav.workflows" },
    ],
  },
  {
    labelKey: "group.developer",
    items: [{ to: "/dev", icon: Code2, key: "nav.apiDocs", href: "/docs" }],
  },
];

export function Layout() {
  const { t, i18n } = useTranslation();
  const token = useAuthStore((s) => s.token);
  const signOut = useAuthStore((s) => s.signOut);
  const [dark, setDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  if (!token) return <Navigate to="/auth" replace />;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border p-3">
        <div className="mb-4 px-2 text-lg font-semibold">LiberAstra</div>
        <nav className="flex flex-1 flex-col gap-3 overflow-y-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.labelKey}>
              <div className="px-2 pb-1 text-xs text-muted-foreground">{t(group.labelKey)}</div>
              {group.items.map((item) =>
                item.href ? (
                  <a
                    key={item.to}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                  >
                    <item.icon className="size-4" />
                    {t(item.key)}
                  </a>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                        isActive && "bg-muted font-medium",
                      )
                    }
                  >
                    <item.icon className="size-4" />
                    {t(item.key)}
                  </NavLink>
                ),
              )}
            </div>
          ))}
        </nav>
        <div className="flex items-center gap-1 border-t border-border pt-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => i18n.changeLanguage(i18n.language.startsWith("zh") ? "en" : "zh")}
            title={t("common.language")}
          >
            <Languages />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setDark((v) => !v)} title={t("common.theme")}>
            {dark ? <Sun /> : <Moon />}
          </Button>
          <Button variant="ghost" size="icon" onClick={signOut} title={t("common.logout")}>
            <LogOut />
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}

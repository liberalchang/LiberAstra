import {
  AudioLines,
  Clapperboard,
  Code2,
  FolderOpen,
  Image,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Moon,
  Settings,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

const NAV_GROUPS = [
  { label: "工作台", items: [{ to: "/dashboard", icon: LayoutDashboard, text: "总览" }] },
  {
    label: "语音",
    items: [
      { to: "/speech/tts", icon: AudioLines, text: "文字转语音" },
      { to: "/speech/asr", icon: AudioLines, text: "语音转文字" },
      { to: "/speech/voices", icon: AudioLines, text: "音色库" },
    ],
  },
  {
    label: "图像",
    items: [{ to: "/image", icon: Image, text: "图像（即将上线）", disabled: true }],
  },
  {
    label: "视频",
    items: [{ to: "/video", icon: Clapperboard, text: "视频（即将上线）", disabled: true }],
  },
  {
    label: "资产库",
    items: [{ to: "/assets", icon: FolderOpen, text: "资产（即将上线）", disabled: true }],
  },
  {
    label: "任务中心",
    items: [{ to: "/jobs", icon: ListChecks, text: "任务（即将上线）", disabled: true }],
  },
  {
    label: "设置",
    items: [{ to: "/settings", icon: Settings, text: "服务提供方" }],
  },
  {
    label: "开发者",
    items: [{ to: "/dev", icon: Code2, text: "API 文档", href: "/docs" }],
  },
] as const;

export function Layout() {
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
            <div key={group.label}>
              <div className="px-2 pb-1 text-xs text-muted-foreground">{group.label}</div>
              {group.items.map((item) =>
                "href" in item ? (
                  <a
                    key={item.to}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                  >
                    <item.icon className="size-4" />
                    {item.text}
                  </a>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    aria-disabled={"disabled" in item && item.disabled}
                    onClick={"disabled" in item && item.disabled ? (e) => e.preventDefault() : undefined}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                        isActive && "bg-muted font-medium",
                        "disabled" in item && item.disabled && "pointer-events-none opacity-40",
                      )
                    }
                  >
                    <item.icon className="size-4" />
                    {item.text}
                  </NavLink>
                ),
              )}
            </div>
          ))}
        </nav>
        <div className="flex items-center gap-1 border-t border-border pt-2">
          <Button variant="ghost" size="icon" onClick={() => setDark((v) => !v)} title="切换主题">
            {dark ? <Sun /> : <Moon />}
          </Button>
          <Button variant="ghost" size="icon" onClick={signOut} title="退出登录">
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

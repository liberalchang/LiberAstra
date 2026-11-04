import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { Field, areaClass } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { NavIcon } from "@/nav/icons";
import type { NavIconKey } from "@/nav/model";

type Mode = "image" | "video" | "speech";

type ModeMeta = {
  icon: NavIconKey;
  targetIcon: NavIconKey;
  labelKey: string;
  hintKey: string;
  target: string;
  targetLabelKey: string;
};

const MODE_META: Record<Mode, ModeMeta> = {
  image: {
    icon: "image",
    targetIcon: "imageGen",
    labelKey: "group.image",
    hintKey: "studio.modeHint.image",
    target: "/image/generate",
    targetLabelKey: "nav.imageGen",
  },
  video: {
    icon: "video",
    targetIcon: "videoQuick",
    labelKey: "group.video",
    hintKey: "studio.modeHint.video",
    target: "/video/quick",
    targetLabelKey: "nav.videoQuick",
  },
  speech: {
    icon: "speech",
    targetIcon: "tts",
    labelKey: "group.speech",
    hintKey: "studio.modeHint.speech",
    target: "/speech/tts",
    targetLabelKey: "nav.tts",
  },
};

const MODES: Mode[] = ["image", "video", "speech"];

type Tool = {
  to: string;
  labelKey: string;
  icon: NavIconKey;
  hintKey: string;
};

type ToolGroup = {
  mode: string;
  labelKey: string;
  icon: NavIconKey;
  tools: Tool[];
};

const TOOL_GROUPS: ToolGroup[] = [
  {
    mode: "image",
    labelKey: "group.image",
    icon: "image",
    tools: [
      { to: "/image/generate", labelKey: "nav.imageGen", icon: "imageGen", hintKey: "studio.toolHints.imageGen" },
      { to: "/image/edit", labelKey: "nav.imageEdit", icon: "imageEdit", hintKey: "studio.toolHints.imageEdit" },
      { to: "/image/depth", labelKey: "nav.imageDepth", icon: "imageDepth", hintKey: "studio.toolHints.imageDepth" },
    ],
  },
  {
    mode: "video",
    labelKey: "group.video",
    icon: "video",
    tools: [
      { to: "/video/quick", labelKey: "nav.videoQuick", icon: "videoQuick", hintKey: "studio.toolHints.videoQuick" },
      { to: "/video/i2v", labelKey: "nav.i2v", icon: "i2v", hintKey: "studio.toolHints.i2v" },
      { to: "/video/avatar", labelKey: "nav.avatar", icon: "avatar", hintKey: "studio.toolHints.avatar" },
      { to: "/video/motion", labelKey: "nav.motion", icon: "motion", hintKey: "studio.toolHints.motion" },
      { to: "/video/assets", labelKey: "nav.videoAssets", icon: "videoAssets", hintKey: "studio.toolHints.videoAssets" },
    ],
  },
  {
    mode: "speech",
    labelKey: "group.speech",
    icon: "speech",
    tools: [
      { to: "/speech/tts", labelKey: "nav.tts", icon: "tts", hintKey: "studio.toolHints.tts" },
      { to: "/speech/asr", labelKey: "nav.asr", icon: "asr", hintKey: "studio.toolHints.asr" },
      { to: "/speech/vc", labelKey: "nav.vc", icon: "vc", hintKey: "studio.toolHints.vc" },
    ],
  },
  {
    mode: "resources",
    labelKey: "group.assets",
    icon: "resources",
    tools: [
      { to: "/assets", labelKey: "nav.assetList", icon: "assetList", hintKey: "studio.toolHints.assetList" },
      { to: "/resources/characters", labelKey: "nav.characters", icon: "characters", hintKey: "studio.toolHints.characters" },
      { to: "/resources/voices", labelKey: "nav.voices", icon: "voices", hintKey: "studio.toolHints.voices" },
      { to: "/resources/music", labelKey: "nav.music", icon: "music", hintKey: "studio.toolHints.music" },
    ],
  },
];

const TOOL_UTILITY_GROUP: ToolGroup = {
  mode: "tools",
  labelKey: "group.tools",
  icon: "tools",
  tools: [
    { to: "/tools/image-concat", labelKey: "nav.imageConcat", icon: "imageConcat", hintKey: "studio.toolHints.imageConcat" },
    { to: "/tools/video-concat", labelKey: "nav.videoConcat", icon: "videoConcat", hintKey: "studio.toolHints.videoConcat" },
    { to: "/tools/audio-concat", labelKey: "nav.audioConcat", icon: "audioConcat", hintKey: "studio.toolHints.audioConcat" },
    { to: "/tools/image-enhance", labelKey: "nav.imageEnhance", icon: "imageEnhance", hintKey: "studio.toolHints.imageEnhance" },
    { to: "/tools/video-enhance", labelKey: "nav.videoEnhance", icon: "videoEnhance", hintKey: "studio.toolHints.videoEnhance" },
  ],
};

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("image");
  const [prompt, setPrompt] = useState("");

  const meta = MODE_META[mode];
  const placeholder =
    mode === "image" ? t("studio.promptImage") : mode === "video" ? t("studio.promptVideo") : t("studio.promptSpeech");
  const carriedState = prompt.trim() ? { prompt } : undefined;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 md:gap-8">
      <header className="surface-bevel relative overflow-hidden rounded-3xl border border-border bg-card p-6 md:p-8">
        <div aria-hidden className="pointer-events-none absolute -top-24 right-10 size-56 rounded-full bg-primary/15 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-24 right-44 size-40 rounded-full bg-primary/10 blur-3xl" />
        <BrandMark className="pointer-events-none absolute right-8 top-1/2 hidden size-24 -translate-y-1/2 text-primary/10 md:block" />
        <div className="relative max-w-3xl">
          <h1 className="text-balance text-3xl font-semibold tracking-tight text-foreground md:text-display">
            {t("studio.title")}
          </h1>
          <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
            {t("studio.subtitle")}
          </p>
        </div>
      </header>

      <section className="surface-bevel relative rounded-2xl border border-border bg-card p-4 ring-1 ring-primary/10 ring-inset md:p-6">
        <div className="grid gap-4 md:grid-cols-[260px_minmax(0,1fr)] md:gap-6">
          <div role="group" aria-label={t("studio.mode")} className="grid grid-cols-3 gap-2 md:flex md:flex-col">
            {MODES.map((value) => {
              const item = MODE_META[value];
              const active = value === mode;
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setMode(value)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-xl border p-2.5 text-left transition-colors md:items-start md:gap-3 md:p-3",
                    active
                      ? "border-primary/40 bg-primary/10 text-primary ring-1 ring-primary/15 ring-inset"
                      : "border-transparent bg-background/50 text-foreground/80 hover:bg-muted",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-8 shrink-0 place-items-center rounded-lg shadow-[inset_0_1px_0_var(--edge-highlight)] ring-1 ring-border/60 md:size-9",
                      active ? "bg-primary/15 text-primary ring-primary/20" : "bg-muted text-muted-foreground",
                    )}
                  >
                    <NavIcon name={item.icon} className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{t(item.labelKey)}</span>
                    <span
                      className={cn(
                        "mt-0.5 hidden text-xs leading-relaxed md:block",
                        active ? "text-primary/80" : "text-muted-foreground",
                      )}
                    >
                      {t(item.hintKey)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="min-w-0">
            <Field label={t("studio.promptLabel")} hint={t("studio.promptHint")}>
              <textarea
                className={cn(areaClass, "min-h-36 resize-none text-base leading-relaxed")}
                placeholder={placeholder}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </Field>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                {t("studio.route")}
                <NavIcon name={meta.targetIcon} className="size-3.5" />
                <span className="font-medium text-foreground">{t(meta.targetLabelKey)}</span>
              </span>
              <Button className="w-full sm:w-auto sm:min-w-36" onClick={() => navigate(meta.target, { state: carriedState })}>
                <ArrowRight />
                {t("studio.start")}
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-foreground">{t("studio.tools")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("studio.toolsHint")}</p>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {TOOL_GROUPS.map((group) => (
            <div key={group.mode} className="surface-bevel relative rounded-2xl border border-border bg-card p-2">
              <div className="flex items-center gap-2 px-2.5 py-2">
                <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary shadow-[inset_0_1px_0_var(--edge-highlight)] ring-1 ring-primary/15">
                  <NavIcon name={group.icon} className="size-3.5" />
                </span>
                <h3 className="text-sm font-semibold text-foreground">{t(group.labelKey)}</h3>
                <span className="ml-auto min-w-5 rounded-full bg-foreground/[0.04] px-1.5 py-0.5 text-center text-[10px] font-medium tabular-nums text-muted-foreground ring-1 ring-border/60">
                  {group.tools.length}
                </span>
              </div>

              <div className="flex flex-col divide-y divide-border/50">
                {group.tools.map((tool) => (
                  <Link
                    key={tool.to}
                    to={tool.to}
                    state={carriedState}
                    title={t(tool.hintKey)}
                    className="group flex items-center gap-3 rounded-xl px-2.5 py-2 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary shadow-[inset_0_1px_0_var(--edge-highlight)] ring-1 ring-primary/15 transition-colors group-hover:bg-primary/15">
                      <NavIcon name={tool.icon} className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-foreground">{t(tool.labelKey)}</span>
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">{t(tool.hintKey)}</span>
                    </span>
                    <ArrowUpRight
                      aria-hidden
                      className="size-3.5 shrink-0 text-muted-foreground/50 transition-[color,transform] duration-150 group-hover:translate-x-0.5 group-hover:text-primary motion-reduce:transition-none"
                    />
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="surface-bevel mt-3 rounded-2xl border border-border bg-card p-2">
          <div className="flex items-center gap-2 px-2.5 py-2">
            <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary shadow-[inset_0_1px_0_var(--edge-highlight)] ring-1 ring-primary/15">
              <NavIcon name={TOOL_UTILITY_GROUP.icon} className="size-3.5" />
            </span>
            <h3 className="text-sm font-semibold text-foreground">{t(TOOL_UTILITY_GROUP.labelKey)}</h3>
            <span className="ml-auto min-w-5 rounded-full bg-foreground/[0.04] px-1.5 py-0.5 text-center text-[10px] font-medium tabular-nums text-muted-foreground ring-1 ring-border/60">
              {TOOL_UTILITY_GROUP.tools.length}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-5">
            {TOOL_UTILITY_GROUP.tools.map((tool) => (
              <Link
                key={tool.to}
                to={tool.to}
                title={t(tool.hintKey)}
                className="group flex items-center gap-2 rounded-xl px-2.5 py-2 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/15">
                  <NavIcon name={tool.icon} className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">{t(tool.labelKey)}</span>
                  <span className="mt-0.5 block truncate text-xs text-muted-foreground">{t(tool.hintKey)}</span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

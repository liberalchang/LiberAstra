import { useQuery } from "@tanstack/react-query";
import { AudioLines, Clapperboard, Image as ImageIcon, Mic } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { FeatureMark, type MarkKind } from "@/components/PageShell";
import { Field } from "@/components/ui/field";
import { cn } from "@/lib/utils";

const TOOLS: { to: string; key: string; kind: MarkKind }[] = [
  { to: "/image/generate", key: "nav.imageGen", kind: "image" },
  { to: "/image/edit", key: "nav.imageEdit", kind: "edit" },
  { to: "/image/upscale", key: "nav.upscale", kind: "upscale" },
  { to: "/video/quick", key: "nav.videoQuick", kind: "video" },
  { to: "/video/i2v", key: "nav.i2v", kind: "i2v" },
  { to: "/video/avatar", key: "nav.avatar", kind: "avatar" },
  { to: "/speech/tts", key: "nav.tts", kind: "tts" },
  { to: "/speech/asr", key: "nav.asr", kind: "asr" },
];

type Mode = "image" | "video" | "speech";

const MODE_ICON = {
  image: ImageIcon,
  video: Clapperboard,
  speech: AudioLines,
} as const;

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: health } = useQuery({ queryKey: ["healthz"], queryFn: api.healthz });
  const [mode, setMode] = useState<Mode>("image");
  const [prompt, setPrompt] = useState("");

  const placeholder =
    mode === "image" ? t("studio.promptImage") : mode === "video" ? t("studio.promptVideo") : t("studio.promptSpeech");
  const ModeIcon = MODE_ICON[mode];

  const go = () => {
    const path = mode === "image" ? "/image/generate" : mode === "video" ? "/video/quick" : "/speech/tts";
    navigate(path, { state: { prompt } });
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
      <section className="rounded-[28px] border border-border bg-card px-5 py-8 md:px-10 md:py-10">
        <div className="mx-auto mb-4 hidden w-fit sm:block">
          <FeatureMark kind={mode === "speech" ? "tts" : mode === "video" ? "video" : "image"} />
        </div>
        <h1 className="text-center text-3xl font-semibold tracking-tight text-foreground md:text-[40px] md:leading-tight">
          {t("studio.title")}
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-muted-foreground md:text-base">
          {t("studio.subtitle")}
          {health ? ` · v${health.version}` : ""}
        </p>

        <div className="mx-auto mt-8 max-w-4xl rounded-2xl border border-border bg-background p-4 md:p-5">
          <div className="mb-3 flex gap-1" role="tablist" aria-label={t("studio.mode")}>
            {(
              [
                ["image", t("group.image")],
                ["video", t("group.video")],
                ["speech", t("group.speech")],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={mode === id}
                className={cn(
                  "inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm text-muted-foreground hover:text-foreground",
                  mode === id && "bg-field text-foreground",
                )}
                onClick={() => setMode(id)}
              >
                {id === "image" ? (
                  <ImageIcon className="size-4" />
                ) : id === "video" ? (
                  <Clapperboard className="size-4" />
                ) : (
                  <AudioLines className="size-4" />
                )}
                {label}
              </button>
            ))}
          </div>
          <Field label={t("studio.promptLabel")} hint={t("studio.promptHint")}>
            <textarea
              className="h-40 w-full resize-none rounded-[10px] border border-border bg-field px-3 py-2 text-lg font-medium text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
              placeholder={placeholder}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </Field>
          <div className="mt-3 flex items-center justify-end">
            <button
              type="button"
              onClick={go}
              className="inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-4 text-base text-primary-foreground hover:bg-primary/90"
            >
              {mode === "speech" ? <Mic className="size-4" /> : mode === "video" ? <Clapperboard className="size-4" /> : <ModeIcon className="size-4" />}
              {t("studio.start")}
            </button>
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">{t("studio.tools")}</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {TOOLS.map((tool) => (
            <Link
              key={tool.to}
              to={tool.to}
              className="flex flex-col items-center gap-2 rounded-2xl border border-border bg-card p-3 text-center hover:bg-muted"
            >
              <FeatureMark kind={tool.kind} />
              <span className="text-sm font-medium text-foreground">{t(tool.key)}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

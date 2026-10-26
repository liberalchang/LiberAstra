import {
  AudioLines,
  Clapperboard,
  Film,
  Image as ImageIcon,
  ImageUp,
  Images,
  BookOpen,
  Library,
  ListTodo,
  Mic,
  Music,
  PersonStanding,
  Settings,
  UserRound,
  WandSparkles,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type MarkKind =
  | "image"
  | "edit"
  | "upscale"
  | "video"
  | "clips"
  | "avatar"
  | "i2v"
  | "motion"
  | "tts"
  | "asr"
  | "voices"
  | "music"
  | "library"
  | "jobs"
  | "settings"
  | "workflow"
  | "guide";

/** 功能图标来自 lucide-react，按主题色着色。 */
const MARK_ICON: Record<MarkKind, LucideIcon> = {
  image: ImageIcon,
  edit: WandSparkles,
  upscale: ImageUp,
  video: Clapperboard,
  clips: Images,
  avatar: UserRound,
  i2v: Film,
  motion: PersonStanding,
  tts: AudioLines,
  asr: Mic,
  voices: Library,
  music: Music,
  library: Images,
  jobs: ListTodo,
  settings: Settings,
  workflow: Workflow,
  guide: BookOpen,
};

export function FeatureMark({ kind }: { kind: MarkKind }) {
  const Icon = MARK_ICON[kind];
  return (
    <div className="grid size-16 place-items-center rounded-2xl bg-primary/15 text-primary" aria-hidden>
      <Icon className="size-8" strokeWidth={1.75} />
    </div>
  );
}

export function PageHeader({
  kind,
  icon: Icon,
  title,
  description,
}: {
  kind: MarkKind;
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <header
      data-kind={kind}
      className="relative flex items-center gap-4 overflow-hidden rounded-3xl border border-border bg-card p-4 md:p-5"
    >
      {/* 装饰性渐变光斑，纯 CSS、随主题色变化 */}
      <div aria-hidden className="pointer-events-none absolute -top-16 right-8 size-44 rounded-full bg-primary/15 blur-3xl" />
      <div aria-hidden className="pointer-events-none absolute -bottom-20 right-32 size-36 rounded-full bg-primary/10 blur-3xl" />
      <div className="relative grid size-16 shrink-0 place-items-center rounded-2xl bg-primary/15 text-primary ring-1 ring-primary/20">
        <Icon className="size-8" strokeWidth={1.75} />
      </div>
      <div className="relative min-w-0 flex-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
    </header>
  );
}

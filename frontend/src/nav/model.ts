export type NavIconKey =
  | "overview"
  | "image"
  | "speech"
  | "video"
  | "resources"
  | "jobs"
  | "settings"
  | "reading"
  | "canvas"
  | "guide"
  | "imageGen"
  | "imageEdit"
  | "upscale"
  | "imageDepth"
  | "tts"
  | "asr"
  | "voices"
  | "music"
  | "videoQuick"
  | "avatar"
  | "i2v"
  | "motion"
  | "videoAssets"
  | "templates"
  | "characters"
  | "assetList"
  | "plugins"
  | "providers"
  | "workflows"
  | "prompts"
  | "system"
  | "apiDocs"
  | "cliDocs";

export type NavLeaf = {
  to: string;
  labelKey: string;
  icon: NavIconKey;
  end?: boolean;
  href?: string;
  external?: boolean;
};

export type NavSection = {
  labelKey?: string;
  items: NavLeaf[];
};

type NavLinkEntry = {
  kind: "link";
  id: string;
  labelKey: string;
  icon: NavIconKey;
  to: string;
  end?: boolean;
  dividerBefore?: boolean;
};

export type NavGroupEntry = {
  kind: "group";
  id: string;
  labelKey: string;
  icon: NavIconKey;
  sections: NavSection[];
  match: string[];
  dividerBefore?: boolean;
};

export type NavEntry = NavLinkEntry | NavGroupEntry;

/**
 * 一级菜单与浮层内容的唯一来源。
 * 顺序、分组和 match 前缀都直接决定侧栏与激活态，改动时先更新 model.test.ts。
 */
export const NAV_ENTRIES: NavEntry[] = [
  {
    kind: "link",
    id: "overview",
    labelKey: "nav.dashboard",
    icon: "overview",
    to: "/dashboard",
    end: true,
  },
  {
    kind: "link",
    id: "canvas",
    labelKey: "nav.canvas",
    icon: "canvas",
    to: "/canvas",
  },
  {
    kind: "group",
    id: "image",
    labelKey: "group.image",
    icon: "image",
    match: ["/image"],
    dividerBefore: true,
    sections: [
      {
        items: [
          { to: "/image/generate", labelKey: "nav.imageGen", icon: "imageGen" },
          { to: "/image/edit", labelKey: "nav.imageEdit", icon: "imageEdit" },
          { to: "/image/upscale", labelKey: "nav.upscale", icon: "upscale" },
          { to: "/image/depth", labelKey: "nav.imageDepth", icon: "imageDepth" },
        ],
      },
    ],
  },
  {
    kind: "group",
    id: "speech",
    labelKey: "group.speech",
    icon: "speech",
    match: ["/speech"],
    sections: [
      {
        items: [
          { to: "/speech/tts", labelKey: "nav.tts", icon: "tts" },
          { to: "/speech/asr", labelKey: "nav.asr", icon: "asr" },
          { to: "/speech/voices", labelKey: "nav.voices", icon: "voices" },
          { to: "/speech/music", labelKey: "nav.music", icon: "music" },
        ],
      },
    ],
  },
  {
    kind: "group",
    id: "video",
    labelKey: "group.video",
    icon: "video",
    match: ["/video"],
    sections: [
      {
        labelKey: "section.videoGenerate",
        items: [
          { to: "/video/quick", labelKey: "nav.videoQuick", icon: "videoQuick" },
          { to: "/video/avatar", labelKey: "nav.avatar", icon: "avatar" },
          { to: "/video/i2v", labelKey: "nav.i2v", icon: "i2v" },
          { to: "/video/motion", labelKey: "nav.motion", icon: "motion" },
          { to: "/video/assets", labelKey: "nav.videoAssets", icon: "videoAssets" },
        ],
      },
      {
        labelKey: "section.videoAssets",
        items: [
          { to: "/video/templates", labelKey: "nav.templates", icon: "templates" },
          { to: "/video/characters", labelKey: "nav.characters", icon: "characters" },
        ],
      },
    ],
  },
  {
    kind: "group",
    id: "resources",
    labelKey: "group.assets",
    icon: "resources",
    match: ["/assets", "/plugins"],
    dividerBefore: true,
    sections: [
      {
        items: [
          { to: "/assets", labelKey: "nav.assetList", icon: "assetList" },
          { to: "/plugins", labelKey: "nav.plugins", icon: "plugins" },
        ],
      },
    ],
  },
  {
    kind: "link",
    id: "jobs",
    labelKey: "nav.jobList",
    icon: "jobs",
    to: "/jobs",
    end: true,
  },
  {
    kind: "group",
    id: "settings",
    labelKey: "group.settings",
    icon: "settings",
    match: ["/settings"],
    dividerBefore: true,
    sections: [
      {
        items: [
          { to: "/settings", labelKey: "nav.providers", icon: "providers", end: true },
          { to: "/settings/workflows", labelKey: "nav.workflows", icon: "workflows" },
          { to: "/settings/prompts", labelKey: "nav.prompts", icon: "prompts" },
          { to: "/settings/system", labelKey: "nav.system", icon: "system" },
        ],
      },
    ],
  },
  {
    kind: "group",
    id: "reading",
    labelKey: "group.reading",
    icon: "reading",
    match: ["/guide", "/dev"],
    sections: [
      {
        items: [
          { to: "/guide", labelKey: "nav.guide", icon: "guide" },
          { to: "/docs", labelKey: "nav.apiDocs", icon: "apiDocs", href: "/docs", external: true },
          { to: "/dev/cli", labelKey: "nav.cliDocs", icon: "cliDocs" },
        ],
      },
    ],
  },
];

function isPrefixMatch(pathname: string, target: string): boolean {
  return pathname === target || pathname.startsWith(target + "/");
}

export function isLeafActive(pathname: string, leaf: NavLeaf): boolean {
  if (leaf.href) return false;
  return leaf.end ? pathname === leaf.to : isPrefixMatch(pathname, leaf.to);
}

export function isGroupActive(pathname: string, group: NavGroupEntry): boolean {
  return group.match.some((prefix) => isPrefixMatch(pathname, prefix));
}

export function isEntryActive(pathname: string, entry: NavEntry): boolean {
  if (entry.kind === "link") {
    return entry.end ? pathname === entry.to : isPrefixMatch(pathname, entry.to);
  }
  return isGroupActive(pathname, entry);
}

export function activeGroupId(pathname: string): string | null {
  const entry = NAV_ENTRIES.find(
    (item): item is NavGroupEntry => item.kind === "group" && isGroupActive(pathname, item),
  );
  return entry?.id ?? null;
}

export function flattenNav(): NavLeaf[] {
  return NAV_ENTRIES.flatMap((entry) => {
    if (entry.kind === "link") {
      return [{ to: entry.to, labelKey: entry.labelKey, icon: entry.icon, end: entry.end }];
    }
    return entry.sections.flatMap((section) => section.items);
  });
}

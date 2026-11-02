import { ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { NavIcon } from "@/nav/icons";
import type { NavLeaf } from "@/nav/model";
import { navSubItemClass } from "./navStyles";

export function NavLeafLink({ leaf, onActivate }: { leaf: NavLeaf; onActivate?: () => void }) {
  const { t } = useTranslation();

  if (leaf.href) {
    return (
      <a
        href={leaf.href}
        target="_blank"
        rel="noreferrer"
        className={navSubItemClass({ active: false })}
        aria-label={`${t(leaf.labelKey)} — ${t("common.opensInNewTab")}`}
        onClick={onActivate}
      >
        <NavIcon name={leaf.icon} className="size-4 shrink-0" />
        <span className="truncate">{t(leaf.labelKey)}</span>
        <ExternalLink className="ml-auto size-3 shrink-0 text-muted-foreground" aria-hidden />
      </a>
    );
  }

  return (
    <NavLink
      to={leaf.to}
      end={leaf.end}
      className={({ isActive }) => navSubItemClass({ active: isActive })}
      onClick={onActivate}
    >
      <NavIcon name={leaf.icon} className="size-4 shrink-0" />
      <span className="truncate">{t(leaf.labelKey)}</span>
    </NavLink>
  );
}

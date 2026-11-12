/** 角色大图查看器：角色库和画布角色节点共用，底部切换视角。 */
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, type CharacterOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { useTx } from "@/i18n/tx";
import { viewLabel, type CharacterView } from "@/lib/characterPrompt";

const VIEW_ORDER: CharacterView[] = [
  "portrait",
  "front",
  "side",
  "back",
  "turnaround",
  "turnaround_grid",
];

export function presentSlots(character: CharacterOut): CharacterView[] {
  return VIEW_ORDER.filter((slot) => character[`${slot}_path`]);
}

export function slotVersions(
  character: CharacterOut,
  slots: CharacterView[],
): Partial<Record<CharacterView, string>> {
  return Object.fromEntries(
    slots.map((slot) => [slot, character[`${slot}_path`] ?? ""]),
  ) as Partial<Record<CharacterView, string>>;
}

export function useSlotUrls(
  id: number | null,
  slots: CharacterView[],
  versions?: Partial<Record<CharacterView, string>>,
): Partial<Record<CharacterView, string>> {
  const [urls, setUrls] = useState<Partial<Record<CharacterView, string>>>({});
  const versionsRef = useRef(versions);
  versionsRef.current = versions;
  const key = slots.join(",");
  const versionKey = slots.map((slot) => versions?.[slot] ?? "").join("|");
  useEffect(() => {
    if (id == null || !key) {
      setUrls({});
      return;
    }
    let active = true;
    const created: string[] = [];
    setUrls({});
    for (const slot of key.split(",").filter(Boolean) as CharacterView[]) {
      api
        .characterImage(id, slot, versionsRef.current?.[slot])
        .then((blob) => {
          if (!active) return;
          const objectUrl = URL.createObjectURL(blob);
          created.push(objectUrl);
          setUrls((prev) => ({ ...prev, [slot]: objectUrl }));
        })
        .catch(() => undefined);
    }
    return () => {
      active = false;
      created.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    };
  }, [id, key, versionKey]);
  return urls;
}

export function CharacterViewer({
  name,
  slots,
  urls,
  current,
  onChange,
  onClose,
}: {
  name: string;
  slots: CharacterView[];
  urls: Partial<Record<CharacterView, string>>;
  current: CharacterView;
  onChange: (slot: CharacterView) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  // 左右方向键切换视角；Esc/滚动锁/焦点管理由 LightboxShell 负责
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const index = slots.indexOf(current);
      if (event.key === "ArrowLeft" && index > 0) onChange(slots[index - 1]);
      if (event.key === "ArrowRight" && index >= 0 && index < slots.length - 1) {
        onChange(slots[index + 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, onChange, slots]);

  const index = slots.indexOf(current);
  const label = tx(viewLabel(current));
  return (
    <LightboxShell onClose={onClose} ariaLabel={`${name} · ${label}`}>
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{name}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
        <Button
          variant="outline"
          size="icon"
          className="rounded-full"
          onClick={onClose}
          title={tx("关闭 (Esc)")}
          aria-label={tx("关闭 (Esc)")}
        >
          <X />
        </Button>
      </div>
      <div className="grid min-h-64 flex-1 place-items-center bg-black/90">
        {urls[current] ? (
          <img src={urls[current]} alt={label} className="max-h-[72vh] w-full object-contain" />
        ) : null}
      </div>
      <div className="flex items-center justify-center gap-2 px-4 py-3">
        <Button
          variant="ghost"
          size="icon"
          disabled={index <= 0}
          onClick={() => onChange(slots[index - 1])}
          aria-label={tx("上一张")}
        >
          <ChevronLeft />
        </Button>
        {slots.map((slot) => (
          <button
            key={slot}
            type="button"
            onClick={() => onChange(slot)}
            className={`rounded-md px-2.5 py-1 text-xs ${
              slot === current
                ? "bg-muted font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tx(viewLabel(slot))}
          </button>
        ))}
        <Button
          variant="ghost"
          size="icon"
          disabled={index < 0 || index >= slots.length - 1}
          onClick={() => onChange(slots[index + 1])}
          aria-label={tx("下一张")}
        >
          <ChevronRight />
        </Button>
      </div>
    </LightboxShell>
  );
}

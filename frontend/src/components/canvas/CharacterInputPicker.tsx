/** 画布角色输入：从角色库选一个人，并指定入镜视角或整张定妆照。 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type CharacterOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { useTx } from "@/i18n/tx";
import { CHARACTER_VIEWS, type CharacterView } from "@/lib/characterPrompt";
import { cn } from "@/lib/utils";

function useSlotThumbs(id: number | null) {
  const [urls, setUrls] = useState<Partial<Record<CharacterView, string>>>({});
  useEffect(() => {
    if (id == null) return;
    let active = true;
    setUrls({});
    const created: string[] = [];
    for (const [slot] of CHARACTER_VIEWS) {
      api
        .characterImage(id, slot)
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
  }, [id]);
  return urls;
}

export function CharacterInputPicker({
  characterId,
  slot,
  onClose,
  onConfirm,
}: {
  characterId: number | null;
  slot: string;
  onClose: () => void;
  onConfirm: (picked: {
    characterId: number;
    characterSlot: CharacterView;
    characterName: string;
    characterDescription: string;
  }) => void;
}) {
  const tx = useTx();
  const { data: characters } = useQuery({ queryKey: ["characters"], queryFn: api.listCharacters });
  const [pickedId, setPickedId] = useState<number | null>(characterId);
  const [pickedSlot, setPickedSlot] = useState<CharacterView>(
    CHARACTER_VIEWS.some(([key]) => key === slot) ? (slot as CharacterView) : "front",
  );
  const current = characters?.find((item) => item.id === pickedId) ?? null;
  const thumbs = useSlotThumbs(current?.id ?? null);

  const confirm = () => {
    if (!current) return;
    onConfirm({
      characterId: current.id,
      characterSlot: pickedSlot,
      characterName: current.name,
      characterDescription: current.description,
    });
  };

  return (
    <LightboxShell onClose={onClose} ariaLabel={tx("选择角色")} className="max-w-lg">
      <div className="flex flex-col gap-4 p-4">
        <h2 className="text-base font-medium">{tx("选择角色")}</h2>
        {!characters?.length ? (
          <div className="flex flex-col gap-3 text-sm text-muted-foreground">
            <p>{tx("角色库还是空的。")}</p>
            <Link to="/video/characters" className="text-primary underline-offset-4 hover:underline" onClick={onClose}>
              {tx("去角色库创建")}
            </Link>
          </div>
        ) : (
          <>
            <div className="flex max-h-40 flex-col gap-1 overflow-auto">
              {characters.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={cn(
                    "rounded-lg border px-3 py-2 text-left text-sm",
                    item.id === pickedId ? "border-primary/40 bg-primary/10" : "border-border",
                  )}
                  onClick={() => setPickedId(item.id)}
                >
                  {item.name}
                </button>
              ))}
            </div>
            {current && <ViewTiles character={current} slot={pickedSlot} thumbs={thumbs} onPick={setPickedSlot} />}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose}>
                {tx("取消")}
              </Button>
              <Button disabled={!current || !hasView(current, pickedSlot)} onClick={confirm}>
                {tx("使用这张图")}
              </Button>
            </div>
          </>
        )}
      </div>
    </LightboxShell>
  );
}

function hasView(character: CharacterOut, slot: CharacterView): boolean {
  return Boolean(character[`${slot}_path`]);
}

function ViewTiles({
  character,
  slot,
  thumbs,
  onPick,
}: {
  character: CharacterOut;
  slot: CharacterView;
  thumbs: Partial<Record<CharacterView, string>>;
  onPick: (slot: CharacterView) => void;
}) {
  const tx = useTx();
  return (
    <div className="grid grid-cols-2 gap-2">
      {CHARACTER_VIEWS.map(([key, label]) => {
        const ready = hasView(character, key);
        return (
          <button
            key={key}
            type="button"
            disabled={!ready}
            className={cn(
              "overflow-hidden rounded-lg border text-left text-xs",
              key === "turnaround" && "col-span-2",
              slot === key ? "border-primary/40 bg-primary/10" : "border-border",
              !ready && "opacity-60",
            )}
            onClick={() => onPick(key)}
          >
            {thumbs[key] ? (
              <img src={thumbs[key]} alt="" className="aspect-video w-full object-cover" />
            ) : (
              <div className="grid aspect-video place-items-center bg-muted/40 text-muted-foreground">
                {ready ? tx("加载中") : tx("尚未生成")}
              </div>
            )}
            <span className="block px-2 py-1.5">{tx(label)}</span>
          </button>
        );
      })}
    </div>
  );
}

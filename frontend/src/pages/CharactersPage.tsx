import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Trash2, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { api, type CharacterOut } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { PromptField, emptyPromptValue, resolveEffectivePrompt, type PromptFieldValue } from "@/components/PromptField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTrackedJob } from "@/hooks/useJob";
import { useTx } from "@/i18n/tx";

const SLOTS = [
  ["portrait", "面部特写"],
  ["front", "正面全身"],
  ["side", "侧面全身"],
  ["back", "背面全身"],
  ["turnaround", "定妆照"],
] as const;

type SlotKey = (typeof SLOTS)[number][0];

function presentSlots(character: CharacterOut): SlotKey[] {
  return SLOTS.filter(([slot]) => character[`${slot}_path`]).map(([slot]) => slot);
}

function useSlotUrls(id: number, slots: SlotKey[]) {
  const [urls, setUrls] = useState<Partial<Record<SlotKey, string>>>({});
  const key = slots.join(",");
  useEffect(() => {
    let active = true;
    const created: string[] = [];
    setUrls({});
    for (const slot of key.split(",").filter(Boolean) as SlotKey[]) {
      api.characterImage(id, slot).then((blob) => {
        if (!active) return;
        const objectUrl = URL.createObjectURL(blob);
        created.push(objectUrl);
        setUrls((prev) => ({ ...prev, [slot]: objectUrl }));
      }).catch(() => undefined);
    }
    return () => {
      active = false;
      created.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    };
  }, [id, key]);
  return urls;
}

function CharacterViewer({
  name,
  slots,
  urls,
  current,
  onChange,
  onClose,
}: {
  name: string;
  slots: { key: SlotKey; label: string }[];
  urls: Partial<Record<SlotKey, string>>;
  current: SlotKey;
  onChange: (slot: SlotKey) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      const index = slots.findIndex((slot) => slot.key === current);
      if (event.key === "ArrowLeft" && index > 0) onChange(slots[index - 1].key);
      if (event.key === "ArrowRight" && index >= 0 && index < slots.length - 1) onChange(slots[index + 1].key);
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [current, onChange, onClose, slots]);

  const label = slots.find((slot) => slot.key === current)?.label ?? "";
  const index = slots.findIndex((slot) => slot.key === current);
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className="relative flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={tx("{name} · {label}", { name, label })}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{name}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
          <Button variant="outline" size="icon" className="rounded-full" onClick={onClose} title={tx("关闭 (Esc)")}>
            <X />
          </Button>
        </div>
        <div className="grid min-h-64 flex-1 place-items-center bg-black/90">
          {urls[current] ? (
            <img src={urls[current]} alt={label} className="max-h-[72vh] w-full object-contain" />
          ) : null}
        </div>
        <div className="flex items-center justify-center gap-2 px-4 py-3">
          <Button variant="ghost" size="icon" disabled={index <= 0} onClick={() => onChange(slots[index - 1].key)} aria-label={tx("上一张")}>
            <ChevronLeft />
          </Button>
          {slots.map((slot) => (
            <button
              key={slot.key}
              type="button"
              onClick={() => onChange(slot.key)}
              className={`rounded-md px-2.5 py-1 text-xs ${slot.key === current ? "bg-muted font-medium" : "text-muted-foreground hover:text-foreground"}`}
            >
              {slot.label}
            </button>
          ))}
          <Button
            variant="ghost"
            size="icon"
            disabled={index < 0 || index >= slots.length - 1}
            onClick={() => onChange(slots[index + 1].key)}
            aria-label={tx("下一张")}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function CharacterCard({ character, onDelete }: { character: CharacterOut; onDelete: () => void }) {
  const tx = useTx();
  const slots = presentSlots(character);
  const urls = useSlotUrls(character.id, slots);
  const [viewing, setViewing] = useState<SlotKey | null>(null);
  const labels = SLOTS.filter(([slot]) => slots.includes(slot)).map(([slot, label]) => ({ key: slot, label: tx(label) }));
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle>{character.name}</CardTitle>
          <CardDescription className="line-clamp-3">{character.description || tx("还没有外观描述")}</CardDescription>
        </div>
        <Button variant="ghost" size="icon" onClick={onDelete} aria-label={tx("删除")}>
          <Trash2 className="size-4" />
        </Button>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {labels.map((slot) =>
          urls[slot.key] ? (
            <button
              key={slot.key}
              type="button"
              onClick={() => setViewing(slot.key)}
              className="flex flex-col gap-1 rounded-md text-left outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
              title={tx("点击查看大图")}
            >
              <img src={urls[slot.key]} alt={slot.label} className="h-28 w-full rounded-md object-contain bg-black/20" />
              <span className="text-center text-xs text-muted-foreground">{slot.label}</span>
            </button>
          ) : null,
        )}
      </CardContent>
      {viewing && (
        <CharacterViewer
          name={character.name}
          slots={labels}
          urls={urls}
          current={viewing}
          onChange={setViewing}
          onClose={() => setViewing(null)}
        />
      )}
    </Card>
  );
}

export function CharactersPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: characters } = useQuery({ queryKey: ["characters"], queryFn: api.listCharacters });
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const [mode, setMode] = useState<"generate" | "upload">("generate");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [promptValue, setPromptValue] = useState<PromptFieldValue>(emptyPromptValue());
  const [turnaround, setTurnaround] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("character-generate");
  const appearance = resolveEffectivePrompt(promptValue);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["characters"] });
  const create = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("name", name);
      form.set("description", description);
      form.set("auto_split", "true");
      if (turnaround) form.set("turnaround", turnaround);
      return api.createCharacter(form);
    },
    onSuccess: () => {
      setName("");
      setDescription("");
      setTurnaround(null);
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err.message),
  });
  const generate = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("name", name);
      form.set("description", appearance);
      form.set("prompt", appearance);
      return api.generateCharacter(form);
    },
    onSuccess: (jobOut) => {
      setName("");
      setPromptValue(emptyPromptValue());
      setError(null);
      setJobId(jobOut.id);
    },
    onError: (err) => setError(err.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteCharacter(id),
    onSuccess: invalidate,
  });
  const running = job && (job.status === "pending" || job.status === "running");
  useEffect(() => {
    if (job?.status === "succeeded") invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader
        kind="avatar"
        icon={UserRound}
        title={tx("角色库")}
        description={tx("保存角色外观和四段式定妆照。视频任务按镜头取一张单人图，不会把整张设定图当成画面。")}
      />
      <Card>
        <CardHeader>
          <CardTitle>{tx("新建角色")}</CardTitle>
          <CardDescription>
            {mode === "generate"
              ? tx("只写年龄、脸型、发型和服装。生成时会补上四段式构图，图像服务在系统设置里配置。")
              : tx("上传已经做好的横版设定图，从左到右是正面全身、侧面全身、背面全身、右侧面部特写。")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Segmented
            ariaLabel={tx("添加方式")}
            value={mode}
            onChange={setMode}
            options={[
              { value: "generate", label: tx("按描述生成") },
              { value: "upload", label: tx("上传设定图") },
            ]}
          />
          <Field label={tx("名称")}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          {mode === "generate" ? (
            <PromptField
              label={tx("外观描述")}
              hint={tx("可先写年龄、脸型、发型、服装，再点优化补成四段式定妆照提示词。")}
              value={promptValue}
              onChange={setPromptValue}
              jobScope="character-sheet:prompt-opt"
              task="character_sheet"
              workflow={prefs?.default_character_workflow || "qwen_image_21"}
              aspect="16:9"
              placeholder={tx("例如：20岁左右，冷白皮，黑色长卷发，奶油白衬衫")}
              minRowsClass="min-h-28"
            />
          ) : (
            <>
              <Field label={tx("四段式设定图")} hint={tx("从左到右：正面全身、侧面全身、背面全身、右侧面部特写。人物之间留出浅色空隙。")}>
                <FileDrop
                  accept="image/*"
                  title={tx("点击或拖拽上传设定图")}
                  names={turnaround ? [turnaround.name] : []}
                  onSelect={(files) => setTurnaround(files?.[0] ?? null)}
                />
              </Field>
              <Field label={tx("外观描述")} hint={tx("选填。快速创作会把这段文字加到每个画面前面。")}>
                <textarea className={`${areaClass} min-h-24`} value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
            </>
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
          {running && <p className="text-sm text-muted-foreground">{tx("生成中… {pct}%", { pct: Math.round((job?.progress ?? 0) * 100) })}</p>}
          {mode === "generate" ? (
            <Button onClick={() => generate.mutate()} disabled={!name || !appearance || generate.isPending || !!running}>
              {tx("生成角色定妆照")}
            </Button>
          ) : (
            <Button onClick={() => create.mutate()} disabled={!name || !turnaround || create.isPending}>
              {tx("保存并自动切分")}
            </Button>
          )}
        </CardContent>
      </Card>
      <div className="grid gap-4">
        {characters?.map((character) => (
          <CharacterCard key={character.id} character={character} onDelete={() => remove.mutate(character.id)} />
        ))}
      </div>
    </div>
  );
}

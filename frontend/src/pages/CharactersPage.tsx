import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/api/client";
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

function SlotImage({ id, slot, label }: { id: number; slot: string; label: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    api.characterImage(id, slot).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => setUrl(null));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, slot]);
  if (!url) return null;
  return (
    <figure className="flex flex-col gap-1">
      <img src={url} alt={label} className="h-28 w-full rounded-md object-contain bg-black/20" />
      <figcaption className="text-center text-xs text-muted-foreground">{label}</figcaption>
    </figure>
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
          <Card key={character.id}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div>
                <CardTitle>{character.name}</CardTitle>
                <CardDescription>{character.description || tx("还没有外观描述")}</CardDescription>
              </div>
              <Button variant="ghost" size="icon" onClick={() => remove.mutate(character.id)} aria-label={tx("删除")}>
                <Trash2 className="size-4" />
              </Button>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {SLOTS.map(([slot, label]) =>
                character[`${slot}_path` as "portrait_path"] ? (
                  <SlotImage key={slot} id={character.id} slot={slot} label={tx(label)} />
                ) : null,
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

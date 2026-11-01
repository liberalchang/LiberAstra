import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type CharacterOut } from "@/api/client";
import { CharacterViewer, presentSlots, useSlotUrls } from "@/components/CharacterViewer";
import { GenerateButton } from "@/components/GenerateButton";
import { PageHeader } from "@/components/PageShell";
import { PromptField, emptyPromptValue, resolveEffectivePrompt, type PromptFieldValue } from "@/components/PromptField";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTrackedJob } from "@/hooks/useJob";
import { useTx } from "@/i18n/tx";
import { viewLabel, type CharacterView } from "@/lib/characterPrompt";
import { workflowPromptPlaceholder } from "@/lib/promptPlaceholder";

function CharacterCard({ character, onDelete }: { character: CharacterOut; onDelete: () => void }) {
  const tx = useTx();
  const slots = presentSlots(character);
  const urls = useSlotUrls(character.id, slots);
  const [viewing, setViewing] = useState<CharacterView | null>(null);
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
        {slots.map((slot) =>
          urls[slot] ? (
            <button
              key={slot}
              type="button"
              onClick={() => setViewing(slot)}
              className="flex flex-col gap-1 rounded-md text-left outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
              title={tx("点击查看大图")}
            >
              <img src={urls[slot]} alt={tx(viewLabel(slot))} className="h-28 w-full rounded-md object-contain bg-black/20" />
              <span className="text-center text-xs text-muted-foreground">{tx(viewLabel(slot))}</span>
            </button>
          ) : null,
        )}
      </CardContent>
      {viewing && (
        <CharacterViewer
          name={character.name}
          slots={slots}
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
  const characterWorkflow = prefs?.default_character_workflow || "qwen_image_21";
  const { data: characterPacks } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.listWorkflows(),
    staleTime: 60_000,
  });
  const characterPack = characterPacks?.find((item) => item.name === characterWorkflow);
  const [mode, setMode] = useState<"generate" | "upload">("generate");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [promptValue, setPromptValue] = useState<PromptFieldValue>(emptyPromptValue());
  const [turnaround, setTurnaround] = useState<File | null>(null);
  const [refs, setRefs] = useState<File[]>([]);
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
      for (const file of refs.slice(0, 3)) form.append("ref_images", file);
      return api.generateCharacter(form);
    },
    onSuccess: (jobOut) => {
      setName("");
      setRefs([]);
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
        kind="characters"
        icon={UsersRound}
        title={tx("角色库")}
        description={tx("保存角色外观和四段式定妆照。视频任务按镜头取一张单人图，不会把整张设定图当成画面。")}
      />
      <Card>
        <CardHeader>
          <CardTitle>{tx("新建角色")}</CardTitle>
          <CardDescription>
            {mode === "generate"
              ? tx("只写年龄、脸型、发型和服装。也可以上传 1 到 3 张参考图，生成时会补上四段式构图。")
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
            <>
            <PromptField
              label={tx("外观描述")}
              hint={tx("可先写年龄、脸型、发型、服装，再点优化补成四段式定妆照提示词。")}
              value={promptValue}
              onChange={setPromptValue}
              jobScope="character-sheet:prompt-opt"
              task="character_sheet"
              workflow={characterWorkflow}
              aspect="16:9"
              placeholder={workflowPromptPlaceholder(tx, characterPack, {
                fallback: "例如：20岁左右，冷白皮，黑色长卷发，奶油白衬衫",
              })}
              minRowsClass="min-h-28"
            />
            <Field label={tx("参考图")} hint={tx("选填，最多 3 张。有参考图时外观描述可以留空。")}>
              <FileDrop
                accept="image/*"
                multiple
                clearAfterSelect
                title={tx("点击或拖拽上传参考图")}
                subtitle={tx("1 张走图生图，2 到 3 张走多图编辑")}
                names={refs.map((file) => file.name)}
                onSelect={(files) => {
                  const picked = Array.from(files ?? []);
                  setRefs((prev) => [...prev, ...picked].slice(0, 3));
                }}
              />
              {refs.length > 0 && (
                <Button variant="ghost" className="mt-2" onClick={() => setRefs([])}>{tx("清空参考图")}</Button>
              )}
            </Field>
            </>
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
          {error && <p className="text-sm text-danger">{error}</p>}
          {mode === "generate" ? (
            <GenerateButton
              className={submitButtonClass}
              running={!!running}
              jobId={job?.id}
              progress={job?.progress}
              disabled={!name || (!appearance && refs.length === 0) || generate.isPending}
              onGenerate={() => generate.mutate()}
              label={tx("生成角色定妆照")}
            />
          ) : (
            <Button className={submitButtonClass} onClick={() => create.mutate()} disabled={!name || !turnaround || create.isPending}>
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

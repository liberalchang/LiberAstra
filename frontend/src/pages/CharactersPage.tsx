import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2, Upload, UsersRound } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, type AssetOut, type CharacterOut } from "@/api/client";
import { AssetPickButton } from "@/components/AssetPickButton";
import { CharacterViewer, presentSlots, slotVersions, useSlotUrls } from "@/components/CharacterViewer";
import { ImagePreviewStrip } from "@/components/ImagePreviewStrip";
import { GenerateButton } from "@/components/GenerateButton";
import { PageHeader } from "@/components/PageShell";
import {
  PromptField,
  emptyPromptValue,
  resolveEffectivePrompt,
  type PromptFieldValue,
  type PromptVar,
} from "@/components/PromptField";
import { Button, submitButtonClass } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTrackedJob } from "@/hooks/useJob";
import { useTx } from "@/i18n/tx";
import { assetAsFile, assetsAsFiles } from "@/lib/assets";
import { viewLabel, type CharacterView } from "@/lib/characterPrompt";

const FOUR_VIEWS = [
  ["portrait", "面部特写"],
  ["front", "正面全身"],
  ["side", "侧面全身"],
  ["back", "背面全身"],
] as const;
type FourView = (typeof FOUR_VIEWS)[number][0];
const FOUR_VIEW_KEYS = FOUR_VIEWS.map(([slot]) => slot);
type CharacterMode = "generate" | "create" | "modify";

function existingPath(character: CharacterOut | null, slot: FourView): string | null {
  if (!character) return null;
  return {
    portrait: character.portrait_path,
    front: character.front_path,
    side: character.side_path,
    back: character.back_path,
  }[slot];
}

async function viewFileError(file: File, label: string): Promise<string | null> {
  const url = URL.createObjectURL(file);
  try {
    const size = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
      image.onerror = () => reject(new Error("无法读取图片"));
      image.src = url;
    });
    if (Math.min(size.width, size.height) < 640) {
      return `${label}短边至少 640px（当前 ${size.width}×${size.height}）`;
    }
    if (Math.abs(size.width * 16 - size.height * 9) > size.height * 9 * 0.01) {
      return `${label}必须是 9:16（当前 ${size.width}×${size.height}）`;
    }
    return null;
  } catch {
    return `${label}不是有效图片`;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function SlotCard({
  label,
  file,
  existingUrl,
  error,
  disabled,
  onSelect,
  onClear,
  onAsset,
}: {
  label: string;
  file?: File;
  existingUrl?: string;
  error?: string;
  disabled: boolean;
  onSelect: (file: File) => void | Promise<void>;
  onClear: () => void;
  onAsset: (asset: AssetOut) => void | Promise<void>;
}) {
  const tx = useTx();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const url = preview ?? existingUrl ?? null;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{tx(label)}</span>
        <span className="text-[10px] text-muted-foreground">9:16 · 短边≥640</span>
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="relative aspect-[9/16] w-full overflow-hidden rounded-lg border border-dashed border-border bg-field/50 text-muted-foreground transition-colors hover:border-primary/50 hover:bg-field disabled:cursor-not-allowed disabled:opacity-60"
      >
        {url ? (
          <img src={url} alt={tx(label)} className="absolute inset-0 size-full object-contain" />
        ) : (
          <span className="flex h-full flex-col items-center justify-center gap-1">
            <Upload className="size-5" />
            <span className="text-xs">{tx("点击上传")}</span>
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const chosen = event.target.files?.[0];
          if (chosen) void onSelect(chosen);
          event.target.value = "";
        }}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          {url ? tx("替换") : tx("上传")}
        </Button>
        {url && (
          <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onClear}>
            {tx("清除")}
          </Button>
        )}
      </div>
      <AssetPickButton
        kind="image"
        disabled={disabled}
        label={tx("资源库")}
        onPick={async (assets) => {
          if (assets[0]) await onAsset(assets[0]);
        }}
      />
    </div>
  );
}

function CharacterCard({ character, onDelete }: { character: CharacterOut; onDelete: () => void }) {
  const tx = useTx();
  const slots = presentSlots(character);
  const urls = useSlotUrls(character.id, slots, slotVersions(character, slots));
  const [viewing, setViewing] = useState<CharacterView | null>(null);
  const download = useMutation({
    mutationFn: async () => {
      const blob = await api.downloadCharacter(character.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `character-${character.id}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle>{character.name}</CardTitle>
          <CardDescription className="line-clamp-3">
            {character.description || tx("还没有外观描述")}
          </CardDescription>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => download.mutate()}
            disabled={!slots.length || download.isPending}
            title={tx("下载角色卡（六图 + character.json）")}
            aria-label={tx("下载角色卡")}
          >
            <Download className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={onDelete} aria-label={tx("删除")}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {slots.map((slot) =>
          urls[slot] ? (
            <button
              key={slot}
              type="button"
              onClick={() => setViewing(slot)}
              className="flex flex-col gap-1 rounded-md text-left outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
              title={tx("点击查看大图")}
            >
              <img
                src={urls[slot]}
                alt={tx(viewLabel(slot))}
                className="h-28 w-full rounded-md bg-black/20 object-contain"
              />
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
  const { data: characterConfig } = useQuery({
    queryKey: ["character-config"],
    queryFn: api.getCharacterConfig,
  });
  const { data: workflowPacks } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.listWorkflows(),
    staleTime: 60_000,
  });

  const [mode, setMode] = useState<CharacterMode>("generate");
  const [selectedId, setSelectedId] = useState(0);
  const [name, setName] = useState("");
  const [appearanceValue, setAppearanceValue] = useState<PromptFieldValue>(emptyPromptValue());
  const [editValue, setEditValue] = useState<PromptFieldValue>(emptyPromptValue());
  const [slotFiles, setSlotFiles] = useState<Partial<Record<FourView, File>>>({});
  const [slotErrors, setSlotErrors] = useState<Partial<Record<FourView, string>>>({});
  const [cleared, setCleared] = useState<Set<FourView>>(new Set());
  const [refFile, setRefFile] = useState<File | null>(null);
  const [descRefs, setDescRefs] = useState<File[]>([]);
  const [targetView, setTargetView] = useState<FourView>("front");
  const [order, setOrder] = useState<"face" | "body">("face");
  const [error, setError] = useState<string | null>(null);
  const { job, setJobId } = useTrackedJob("character-generate");

  const selected = characters?.find((item) => item.id === selectedId) ?? null;
  const existingSlots = useMemo(
    () =>
      (selected
        ? presentSlots(selected).filter((slot): slot is FourView =>
            FOUR_VIEW_KEYS.includes(slot as FourView),
          )
        : []) as FourView[],
    [selected],
  );
  const existingUrls = useSlotUrls(
    selected?.id ?? null,
    existingSlots,
    selected ? slotVersions(selected, existingSlots) : undefined,
  );
  const effectiveHas = useMemo(() => {
    const has = {} as Record<FourView, boolean>;
    for (const slot of FOUR_VIEW_KEYS) {
      has[slot] =
        Boolean(slotFiles[slot]) || Boolean(!cleared.has(slot) && existingPath(selected, slot));
    }
    return has;
  }, [cleared, selected, slotFiles]);

  const appearance = resolveEffectivePrompt(appearanceValue);
  const editText = resolveEffectivePrompt(editValue);
  const allSlots = FOUR_VIEW_KEYS.every((slot) => effectiveHas[slot]);
  const hasHead = effectiveHas.portrait || effectiveHas.front;
  const needsGeneration =
    mode === "generate" ||
    (mode === "create" && !allSlots) ||
    (mode === "modify" && (Boolean(editText.trim()) || !allSlots));
  const missingConfig = characterConfig?.missing ?? [];
  const configBlocked = needsGeneration && missingConfig.length > 0;

  const editWorkflow =
    Object.values(effectiveHas).filter(Boolean).length > 1
      ? characterConfig?.workflows?.multi
      : characterConfig?.workflows?.single;
  const editPack = workflowPacks?.find((pack) => pack.name === editWorkflow);
  const mentions = Object.values(editPack?.inputs ?? {})
    .filter((spec) => spec.type === "image")
    .map((spec, index) => spec.mention || spec.label || `image ${index + 1}`);

  const resourceRoles = useMemo(() => {
    const roles: Array<{ type: "view"; slot: FourView } | { type: "ref" }> = [];
    if (effectiveHas[targetView]) roles.push({ type: "view", slot: targetView });
    if (refFile) roles.push({ type: "ref" });
    for (const slot of FOUR_VIEW_KEYS) {
      if (slot !== targetView && effectiveHas[slot]) roles.push({ type: "view", slot });
    }
    return roles;
  }, [effectiveHas, refFile, targetView]);
  const editResources: PromptVar[] = resourceRoles.map((role, index) => ({
    name: role.type === "ref" ? "supplement" : role.slot,
    kind: "image",
    tag: mentions[index] ?? `image ${index + 1}`,
    preview:
      role.type === "ref"
        ? refFile?.name || tx("补充参考图")
        : `${viewLabel(role.slot)}${slotFiles[role.slot]?.name ? ` · ${slotFiles[role.slot]?.name}` : " · 角色图"}`,
  }));

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["characters"] });
  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("name", name.trim());
      form.set("description", appearance);
      form.set("order", order);
      if (mode !== "generate") {
        if (mode === "modify" && selectedId) form.set("character_id", String(selectedId));
        for (const slot of FOUR_VIEW_KEYS) {
          const file = slotFiles[slot];
          if (file) form.set(slot, file);
        }
        if (cleared.size) form.set("cleared_slots", [...cleared].join(","));
        if (refFile) form.set("ref_image", refFile);
        if (mode === "modify" && editText.trim()) {
          form.set("prompt", editText);
          form.set("target_view", targetView);
        }
      } else {
        for (const file of descRefs) form.append("ref_images", file);
      }
      return api.generateCharacter(form);
    },
    onSuccess: (jobOut) => {
      setError(null);
      setJobId(jobOut.id);
      setSlotFiles({});
      setSlotErrors({});
      setCleared(new Set());
      setRefFile(null);
      setDescRefs([]);
      setEditValue(emptyPromptValue());
    },
    onError: (err) => {
      if (err instanceof Error && err.message.includes("character_config_missing")) {
        setError(tx("角色生图配置不完整，请到系统设置补齐。"));
      } else {
        setError(err.message);
      }
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteCharacter(id),
    onSuccess: invalidate,
  });

  const running = Boolean(job && (job.status === "pending" || job.status === "running"));
  const configured = missingConfig.length === 0;
  useEffect(() => {
    if (job?.status === "succeeded") void invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  const resetSelection = () => {
    setSelectedId(0);
    setName("");
    setAppearanceValue(emptyPromptValue());
    setEditValue(emptyPromptValue());
    setSlotFiles({});
    setSlotErrors({});
    setCleared(new Set());
    setRefFile(null);
    setError(null);
  };

  const chooseCharacter = (id: number) => {
    const chosen = characters?.find((item) => item.id === id) ?? null;
    setSelectedId(id);
    setName(chosen?.name ?? "");
    setAppearanceValue({ ...emptyPromptValue(), raw: chosen?.description ?? "" });
    setEditValue(emptyPromptValue());
    setSlotFiles({});
    setSlotErrors({});
    setCleared(new Set());
    setRefFile(null);
    setError(null);
    const first = existingPath(chosen, "front")
      ? "front"
      : FOUR_VIEWS.find(([slot]) => Boolean(existingPath(chosen, slot)))?.[0] ?? "front";
    setTargetView(first);
  };

  const switchMode = (next: CharacterMode) => {
    setMode(next);
    resetSelection();
    setDescRefs([]);
  };

  const chooseSlot = async (slot: FourView, file: File) => {
    const message = await viewFileError(file, viewLabel(slot));
    if (message) {
      setSlotErrors((prev) => ({ ...prev, [slot]: message }));
      return;
    }
    setError(null);
    setSlotErrors((prev) => {
      const next = { ...prev };
      delete next[slot];
      return next;
    });
    setSlotFiles((prev) => ({ ...prev, [slot]: file }));
    setCleared((prev) => {
      const next = new Set(prev);
      next.delete(slot);
      return next;
    });
    setTargetView(slot);
  };

  const clearSlot = (slot: FourView) => {
    setSlotFiles((prev) => {
      const next = { ...prev };
      delete next[slot];
      return next;
    });
    setSlotErrors((prev) => {
      const next = { ...prev };
      delete next[slot];
      return next;
    });
    setCleared((prev) => new Set(prev).add(slot));
    setError(null);
  };

  const mergeDescRefs = (incoming: File[]) => {
    setDescRefs((prev) => {
      const seen = new Set(prev.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const next = [...prev];
      for (const file of incoming) {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!seen.has(key)) {
          seen.add(key);
          next.push(file);
        }
      }
      if (next.length > 3) setError(tx("参考图最多 3 张"));
      return next.slice(0, 3);
    });
  };

  const editTargetMissing =
    mode === "modify" && Boolean(editText.trim()) && !effectiveHas[targetView];
  const submitDisabled =
    !name.trim() ||
    submit.isPending ||
    configBlocked ||
    (mode === "generate"
      ? !appearance.trim() && descRefs.length === 0
      : mode === "create"
        ? !hasHead
        : !selectedId || !hasHead || editTargetMissing);
  const actionLabel =
    mode === "generate"
      ? tx("生成角色设定图")
      : mode === "create"
        ? allSlots
          ? tx("合成并创建")
          : tx("补全并创建")
        : editText.trim()
          ? tx("按提示词修改并保存")
          : allSlots
            ? tx("重新合成并保存")
            : tx("补全缺失视角并保存");
  const jobText = typeof job?.outputs?.[0]?.content === "string" ? job.outputs[0].content : "";
  const jobStatusLabel = running
    ? tx("角色任务运行中")
    : job?.status === "succeeded"
      ? tx("上次任务已完成")
      : job?.status === "failed"
        ? tx("上次任务失败")
        : "";

  return (
    <div className="flex max-w-6xl flex-col gap-6">
      <PageHeader
        kind="characters"
        icon={UsersRound}
        title={tx("角色库")}
        description={tx(
          "按描述生成新角色、上传四视图新建，或从角色库选择已有角色修改。四张 9:16 单人图顺序生成，程序合成四宫格，再生成 16:9 定妆照。",
        )}
      />
      <Card>
        <CardHeader>
          <CardTitle>
            {mode === "generate"
              ? tx("按描述生成")
              : mode === "create"
                ? tx("上传新建")
                : tx("修改已有角色")}
          </CardTitle>
          <CardDescription>
            {mode === "generate"
              ? tx("先写外观，再按面部优先或全身优先生成四张单人图。有参考图时可从参考图开始。")
              : mode === "create"
                ? tx("上传四槽并补全缺失视角，创建新角色；外观描述是长期身份基准。")
                : tx("从角色库选择角色，带入四图；可替换图片、补全缺失视角，或只按提示词修改目标视角。")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Segmented
            ariaLabel={tx("角色库操作")}
            value={mode}
            onChange={(value) => {
              if (value === "generate" || value === "create" || value === "modify") {
                switchMode(value);
              }
            }}
            options={[
              { value: "generate", label: tx("按描述生成") },
              { value: "create", label: tx("上传新建") },
              { value: "modify", label: tx("修改已有角色") },
            ]}
          />

          {!configured && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
              <p className="font-medium text-warning">{tx("角色生图配置不完整")}</p>
              <p className="mt-1 text-muted-foreground">
                {tx("缺少：{items}。", { items: missingConfig.join("、") })}
                <Link className="ml-1 underline underline-offset-2" to="/settings/system">
                  {tx("去系统设置")}
                </Link>
                {!needsGeneration && ` ${tx("四槽齐全且不修改时仍可直接合成。")}`}
              </p>
            </div>
          )}

          {jobStatusLabel && (
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{jobStatusLabel}</span>
                {running && (
                  <span className="text-muted-foreground">
                    {Math.round((job?.progress ?? 0) * 100)}%
                  </span>
                )}
              </div>
              {jobText && <p className="mt-1 text-muted-foreground">{jobText}</p>}
              {job?.status === "failed" && job.error && (
                <p className="mt-1 text-danger">{job.error}</p>
              )}
            </div>
          )}

          {mode === "modify" && (
            <Field
              label={tx("选择角色")}
              hint={tx("从角色库选择要修改的角色；保存会覆盖原角色。")}
            >
              <select
                className={selectClass}
                value={selectedId}
                onChange={(event) => chooseCharacter(Number(event.target.value))}
              >
                <option value={0}>{tx("请选择角色")}</option>
                {characters?.map((character) => (
                  <option key={character.id} value={character.id}>
                    {character.name}
                  </option>
                ))}
              </select>
            </Field>
          )}

          {mode === "modify" && !selectedId && (
            <p className="text-sm text-muted-foreground">
              {tx("选择角色后可替换四槽图片、补全缺失视角，或填写修改提示词。")}
            </p>
          )}

          {mode !== "generate" && (mode === "create" || selectedId > 0) && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {FOUR_VIEWS.map(([slot, label]) => (
                  <SlotCard
                    key={slot}
                    label={label}
                    file={slotFiles[slot]}
                    existingUrl={existingUrls[slot]}
                    error={slotErrors[slot]}
                    disabled={running}
                    onSelect={(file) => chooseSlot(slot, file)}
                    onClear={() => clearSlot(slot)}
                    onAsset={async (asset) => chooseSlot(slot, await assetAsFile(asset))}
                  />
                ))}
              </div>
              <Field
                label={tx("补充参考图（可选，1 张）")}
                hint={tx("不受 9:16 和 640px 限制，只用于提供服装或身份细节。")}
              >
                <FileDrop
                  accept="image/*"
                  clearAfterSelect
                  title={tx("点击或拖拽上传补充参考图")}
                  subtitle={tx("1 张")}
                  onSelect={(files) => setRefFile(files?.[0] ?? null)}
                  disabled={running}
                />
                <AssetPickButton
                  kind="image"
                  disabled={running}
                  onPick={async (assets) => {
                    if (assets[0]) setRefFile(await assetAsFile(assets[0]));
                  }}
                />
                {refFile && (
                  <ImagePreviewStrip files={[refFile]} onRemove={() => setRefFile(null)} />
                )}
              </Field>
            </>
          )}

          {(mode !== "modify" || selectedId > 0) && (
            <Field label={tx("名称")}>
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={tx("角色名称")}
                disabled={running}
              />
            </Field>
          )}

          {mode === "modify" ? (
            selectedId ? (
              <details className="rounded-lg border border-border bg-muted/20">
                <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                  {tx("角色外观基准（长期；用于补全缺失视角和后续视频）")}
                </summary>
                <div className="flex flex-col gap-2 border-t border-border p-3">
                  <PromptField
                    label={tx("外观描述")}
                    hint={tx("保存后会更新角色描述，但不会自动重绘其它视角。只写年龄、脸型、发型、身材和服装。")}
                    value={appearanceValue}
                    onChange={setAppearanceValue}
                    jobScope="character-appearance"
                    task="character_appearance"
                    placeholder={tx("例如：20岁左右，冷白皮，黑色长卷发，奶油白衬衫")}
                    minRowsClass="min-h-20"
                    disabled={running}
                  />
                </div>
              </details>
            ) : null
          ) : (
            <PromptField
              label={tx("外观描述")}
              hint={tx("只写年龄、脸型、发型、身材和服装，不写排版；可点 ✨ 优化。")}
              value={appearanceValue}
              onChange={setAppearanceValue}
              jobScope="character-appearance"
              task="character_appearance"
              placeholder={tx("例如：20岁左右，冷白皮，黑色长卷发，奶油白衬衫")}
              minRowsClass="min-h-24"
              disabled={running}
            />
          )}

          {mode === "generate" && (
            <Field
              label={tx("参考图")}
              hint={tx("选填，最多 3 张。有参考图时外观描述可以留空。")}
            >
              <FileDrop
                accept="image/*"
                multiple
                clearAfterSelect
                title={tx("点击或拖拽上传参考图")}
                subtitle={tx("1 到 3 张")}
                onSelect={(files) => mergeDescRefs(Array.from(files ?? []))}
                disabled={running}
              />
              <AssetPickButton
                kind="image"
                multiple
                disabled={running}
                onPick={async (assets) => mergeDescRefs(await assetsAsFiles(assets))}
              />
              <ImagePreviewStrip
                files={descRefs}
                onRemove={(index) => setDescRefs((prev) => prev.filter((_, i) => i !== index))}
              />
            </Field>
          )}

          {mode === "modify" && selectedId > 0 && (
            <>
              <PromptField
                label={tx("修改提示词")}
                hint={tx(
                  "填写后只改目标视角；不填则补全缺失视角。键入 / 引用当前页图片，也接受 <Picture N> 别名。",
                )}
                value={editValue}
                onChange={setEditValue}
                jobScope="character-edit"
                task="character_edit"
                workflow={editWorkflow}
                resources={editResources}
                placeholder={tx("例如：把 image 1 的外套改成红色，其他保持不变")}
                minRowsClass="min-h-24"
                disabled={running}
              />
              {editText.trim() && (
                <Field label={tx("目标视角")} hint={tx("只修改这一张，其它视角保持原图。")}>
                  <select
                    className={selectClass}
                    value={targetView}
                    onChange={(event) => setTargetView(event.target.value as FourView)}
                    disabled={running}
                  >
                    {FOUR_VIEWS.map(([slot, label]) => (
                      <option key={slot} value={slot}>
                        {tx(label)}
                        {effectiveHas[slot] ? "" : tx("（未上传）")}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
            </>
          )}

          {!editText.trim() && (mode !== "modify" || selectedId > 0) && (
            <Field
              label={tx("生成顺序")}
              hint={tx("面部优先：特写 → 正面 → 侧面 → 背面；全身优先从正面开始。")}
            >
              <Segmented
                ariaLabel={tx("生成顺序")}
                value={order}
                onChange={(value) => {
                  if (value === "face" || value === "body") setOrder(value);
                }}
                options={[
                  { value: "face", label: tx("面部优先") },
                  { value: "body", label: tx("全身优先") },
                ]}
              />
            </Field>
          )}

          {error && <p className="text-sm text-danger">{error}</p>}

          <GenerateButton
            className={submitButtonClass}
            running={running}
            jobId={job?.id}
            progress={job?.progress}
            disabled={submitDisabled}
            onGenerate={() => submit.mutate()}
            label={actionLabel}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {characters?.map((character) => (
          <CharacterCard
            key={character.id}
            character={character}
            onDelete={() => remove.mutate(character.id)}
          />
        ))}
      </div>
    </div>
  );
}

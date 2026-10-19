import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { cn } from "@/lib/utils";

export type PromptFieldValue = {
  raw: string;
  optimized: string;
  /** 生成 optimized 时对应的 raw 快照；用于判断是否过期 */
  optimizedFromRaw: string;
  useOptimized: boolean;
};

export function emptyPromptValue(raw = ""): PromptFieldValue {
  return { raw, optimized: "", optimizedFromRaw: "", useOptimized: false };
}

/** 提交时实际生效的提示词 */
export function resolveEffectivePrompt(v: PromptFieldValue): string {
  if (v.useOptimized && v.optimized.trim()) return v.optimized.trim();
  return v.raw.trim();
}

type Props = {
  label?: string;
  hint?: string;
  value: PromptFieldValue;
  onChange: (next: PromptFieldValue) => void;
  /** 后端 task id，如 t2i / i2v / quick_topic —— 决定功能级系统提示词 */
  task: string;
  /** 当前工作流包名；后端会注入模型家族与 Guide 等上下文 */
  workflow?: string;
  aspect?: string;
  /** 额外上下文（如非 Comfy 的图像 Provider 类型） */
  extraContext?: string;
  placeholder?: string;
  minRowsClass?: string;
  disabled?: boolean;
};

/**
 * 统一提示词控件：原始 / 优化双 Tab、场景下拉、✨ 紧挨「优化后提示词」、是否使用优化稿执行。
 */
export function PromptField({
  label = "提示词",
  hint,
  value,
  onChange,
  task,
  workflow,
  aspect,
  extraContext,
  placeholder,
  minRowsClass = "min-h-24",
  disabled,
}: Props) {
  const [tab, setTab] = useState<"raw" | "optimized">("raw");
  const [scene, setScene] = useState("auto");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const { data: catalog } = useQuery({
    queryKey: ["prompts-catalog"],
    queryFn: api.listPrompts,
    staleTime: 60_000,
  });
  const scenes = catalog?.scenes ?? [];
  const taskLabel = catalog?.tasks?.find((t) => t.id === task)?.name;

  const stale =
    Boolean(value.optimized.trim()) &&
    value.raw !== value.optimizedFromRaw &&
    value.optimizedFromRaw !== "";

  const displayText = tab === "raw" ? value.raw : value.optimized;

  const optimize = useMutation({
    mutationFn: () =>
      api.optimizePrompt({
        prompt: value.raw,
        task,
        scene: scene === "auto" ? undefined : scene,
        workflow,
        aspect,
        extra_context: extraContext,
      }),
    onMutate: () => {
      setTab("optimized");
      setStatusMsg("正在优化提示词…");
    },
    onSuccess: (r) => {
      setStatusMsg(r.provider_name ? `已由 ${r.provider_name} / ${r.model} 生成` : null);
      onChange({
        ...value,
        optimized: r.optimized,
        optimizedFromRaw: value.raw,
        useOptimized: true,
      });
    },
    onError: (err) => {
      setStatusMsg(err.message || "优化失败");
    },
  });

  const sceneOptions = useMemo(() => {
    if (scenes.length) return scenes;
    return [{ id: "auto", name: "自动 / 通用", append: "" }];
  }, [scenes]);

  return (
    <Field
      label={label}
      hint={
        hint ??
        `点击 ✨ 按当前功能${taskLabel ? `（${taskLabel}）` : ""}与所选工作流优化；场景预设仅叠加风格倾向。「自动」不改功能模板。`
      }
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* Tab 与 ✨ 同一组，避免星号单独换行 */}
          <div className="inline-flex items-center rounded-lg border border-border p-0.5 text-sm">
            <button
              type="button"
              className={cn(
                "rounded-md px-2.5 py-1 transition-colors",
                tab === "raw" ? "bg-muted font-medium" : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setTab("raw")}
            >
              原始输入
            </button>
            <button
              type="button"
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                tab === "optimized"
                  ? "bg-muted font-medium"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setTab("optimized")}
            >
              优化后提示词
              {stale && (
                <span
                  className="size-1.5 rounded-full bg-amber-500"
                  title="原始输入已变更，优化稿可能过期"
                />
              )}
            </button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="ml-0.5 size-8 shrink-0"
              title="用系统默认 LLM 优化提示词（覆盖「优化后提示词」）"
              disabled={disabled || !value.raw.trim() || optimize.isPending}
              onClick={() => optimize.mutate()}
            >
              <Sparkles className="size-4" />
            </Button>
          </div>
          <select
            className={`${selectClass} w-auto min-w-[8rem]`}
            value={scene}
            onChange={(e) => setScene(e.target.value)}
            title="场景风格预设（叠加在功能模板之上；自动=不强制某一场景）"
          >
            {sceneOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {optimize.isPending && tab === "optimized" ? (
          <div
            className={cn(
              areaClass,
              minRowsClass,
              "flex items-center justify-center text-sm text-muted-foreground",
            )}
          >
            {statusMsg ?? "正在优化提示词…"}
          </div>
        ) : (
          <textarea
            className={cn(areaClass, minRowsClass)}
            placeholder={
              tab === "raw"
                ? (placeholder ?? "输入简短描述…")
                : "点击 ✨ 生成优化提示词，也可在此直接编辑"
            }
            value={displayText}
            onChange={(e) => {
              const text = e.target.value;
              if (tab === "raw") {
                onChange({ ...value, raw: text });
              } else {
                onChange({ ...value, optimized: text });
              }
            }}
          />
        )}

        {statusMsg && !optimize.isPending && (
          <p
            className={cn(
              "text-xs",
              statusMsg.includes("失败") || statusMsg.includes("错误") || statusMsg.includes("尚未")
                ? "text-red-500"
                : "text-muted-foreground",
            )}
          >
            {statusMsg}
          </p>
        )}
        {stale && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            原始输入已变更，优化稿可能过期。点击 ✨ 重新生成覆盖，或关闭下方开关使用原始输入。
          </p>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={value.useOptimized}
            disabled={!value.optimized.trim()}
            onChange={(e) => onChange({ ...value, useOptimized: e.target.checked })}
          />
          使用优化后提示词执行任务
        </label>
      </div>
    </Field>
  );
}

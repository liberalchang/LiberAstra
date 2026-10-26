import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api, TERMINAL_STATUSES } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { useTrackedJob } from "@/hooks/useJob";
import {
  type PromptFieldValue,
  emptyPromptValue,
  coercePromptValue,
  resolveEffectivePrompt,
} from "@/lib/promptValue";
import { cn } from "@/lib/utils";
import { useTx } from "@/i18n/tx";

export type { PromptFieldValue };
export { emptyPromptValue, coercePromptValue, resolveEffectivePrompt };

/** 画布变量:`/` 补全列表项;媒体变量插入 <Picture 1> 风格标签,文本变量插入 {{名}} */
export interface PromptVar {
  name: string;
  preview: string;
  /** 媒体变量:插入 <Picture 1> 风格标签而不是 {{名}} */
  tag?: string;
}

type Props = {
  label?: string;
  hint?: string;
  value: PromptFieldValue;
  onChange: (next: PromptFieldValue) => void;
  /** sessionStorage 任务作用域；刷新后凭此恢复进行中的优化 Job */
  jobScope: string;
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
  /** 画布已连接节点的变量:给了它,原始输入支持 / 唤起补全插入 */
  variables?: PromptVar[];
};

/**
 * 统一提示词控件：原始 / 优化双 Tab、场景下拉、✨ 提交 prompt.optimize Job。
 * 父组件应持久化完整 value；进行中任务靠 jobScope + useTrackedJob 跨刷新恢复。
 */
export function PromptField({
  label = "提示词",
  hint,
  value,
  onChange,
  jobScope,
  task,
  workflow,
  aspect,
  extraContext,
  placeholder,
  minRowsClass = "min-h-24",
  disabled,
  variables,
}: Props) {
  const tx = useTx();
  const [tab, setTab] = useState<"raw" | "optimized">(() =>
    value.useOptimized && value.optimized.trim() ? "optimized" : "raw",
  );
  const [scene, setScene] = useState("auto");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  // 画布变量补全:"/" 的光标位置与菜单高亮项(仅原始输入 Tab)
  const [menuAt, setMenuAt] = useState<number | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const valueRef = useRef(value);
  valueRef.current = value;
  /** 已把某次成功 Job 写入 value，避免轮询重复 onChange */
  const appliedJobRef = useRef<string | null>(null);
  const lastPersistAt = useRef(0);

  const { job, setJobId } = useTrackedJob(jobScope);
  const running = Boolean(job && (job.status === "pending" || job.status === "running"));

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

  const jobContent =
    typeof job?.outputs?.[0]?.content === "string" ? job.outputs[0].content : "";
  const displayText =
    tab === "raw"
      ? value.raw
      : running && jobContent
        ? jobContent
        : value.optimized;

  const persistPartial = (text: string, rawSnapshot: string) => {
    const now = Date.now();
    if (now - lastPersistAt.current < 400) return;
    lastPersistAt.current = now;
    onChange({
      ...valueRef.current,
      optimized: text,
      optimizedFromRaw: rawSnapshot,
      useOptimized: true,
    });
  };

  // 进行中：把 outputs 增量同步到本地缓存与状态文案
  useEffect(() => {
    if (!job) return;
    const rawSnapshot = String(job.params?.prompt ?? valueRef.current.raw);
    const out = job.outputs?.[0];
    const content = typeof out?.content === "string" ? out.content : "";
    const providerLabel = [out?.provider_name, out?.model ?? job.model]
      .filter(Boolean)
      .join(" / ");

    if (job.status === "pending") {
      setTab("optimized");
      setStatusMsg(tx("优化任务排队中…"));
      return;
    }
    if (job.status === "running") {
      setTab("optimized");
      setStatusMsg(
        providerLabel
          ? tx("正在生成（{who}）· {n} 字", { who: providerLabel, n: content.length })
          : content
            ? tx("正在生成… {n} 字", { n: content.length })
            : tx("正在生成…"),
      );
      if (content) persistPartial(content, rawSnapshot);
      return;
    }
    if (job.status === "succeeded" && appliedJobRef.current !== job.id) {
      appliedJobRef.current = job.id;
      const finalText = content.trim();
      onChange({
        ...valueRef.current,
        optimized: finalText,
        optimizedFromRaw: rawSnapshot,
        useOptimized: Boolean(finalText),
      });
      setTab("optimized");
      setStatusMsg(
        finalText
          ? providerLabel
            ? tx("已由 {who} 生成", { who: providerLabel })
            : tx("优化完成")
          : tx("模型返回为空，请重试或换模型"),
      );
      setJobId(null);
      return;
    }
    if (job.status === "failed") {
      setStatusMsg(job.error || tx("优化失败"));
      setJobId(null);
      return;
    }
    if (job.status === "canceled") {
      setStatusMsg(tx("已取消"));
      setJobId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅随 job 快照变化
  }, [job]);

  // 刷新后若仍有进行中任务，切到优化 Tab
  useEffect(() => {
    if (running) setTab("optimized");
  }, [running]);

  const optimize = useMutation({
    mutationFn: () =>
      api.optimizePrompt({
        prompt: valueRef.current.raw,
        task,
        scene: scene === "auto" ? undefined : scene,
        workflow,
        aspect,
        extra_context: extraContext,
      }),
    onMutate: () => {
      setTab("optimized");
      setStatusMsg(tx("正在提交优化任务…"));
      appliedJobRef.current = null;
      lastPersistAt.current = 0;
    },
    onSuccess: (j) => {
      setJobId(j.id);
      setStatusMsg(tx("优化任务已提交…"));
    },
    onError: (err) => {
      setStatusMsg(err.message || tx("提交失败"));
    },
  });

  const sceneOptions = useMemo(() => {
    if (scenes.length) return scenes;
    return [{ id: "auto", name: tx("自动 / 通用"), append: "" }];
  }, [scenes]);

  const busy = running || optimize.isPending;

  const insertVar = (v: PromptVar) => {
    if (menuAt == null) return;
    const snippet = v.tag ?? `{{${v.name}}}`;
    const raw = valueRef.current.raw;
    onChange({ ...valueRef.current, raw: `${raw.slice(0, menuAt)}${snippet}${raw.slice(menuAt + 1)}` });
    setMenuAt(null);
    areaRef.current?.focus();
  };

  return (
    <Field
      label={tx(label)}
      hint={
        hint ??
        tx("点击 ✨ 按当前功能{task}与所选工作流优化；场景预设仅叠加风格倾向。「自动」不改功能模板。", {
          task: taskLabel ? `（${tx(taskLabel)}）` : "",
        })
      }
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center rounded-lg border border-border p-0.5 text-sm">
            <button
              type="button"
              className={cn(
                "rounded-md px-2.5 py-1 transition-colors",
                tab === "raw" ? "bg-muted font-medium" : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setTab("raw")}
            >
              {tx("原始输入")}
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
              {tx("优化后提示词")}
              {stale && (
                <span
                  className="size-1.5 rounded-full bg-warning"
                  title={tx("原始输入已变更，优化稿可能过期")}
                />
              )}
            </button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="ml-0.5 size-8 shrink-0"
              title={tx("用系统默认 LLM 优化提示词（覆盖「优化后提示词」）")}
              disabled={disabled || !value.raw.trim() || busy}
              onClick={() => optimize.mutate()}
            >
              <Sparkles className={cn("size-4", busy && "animate-pulse")} />
            </Button>
          </div>
          <select
            className={`${selectClass} w-auto min-w-[8rem]`}
            value={scene}
            onChange={(e) => setScene(e.target.value)}
            title={tx("场景风格预设（叠加在功能模板之上；自动=不强制某一场景）")}
            disabled={busy}
          >
            {sceneOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {tx(s.name)}
              </option>
            ))}
          </select>
        </div>

        <div className="relative">
          <textarea
            ref={areaRef}
            className={cn(areaClass, minRowsClass)}
            placeholder={
              tab === "raw"
                ? (placeholder ??
                  (variables?.length
                    ? tx("输入简短描述…键入 / 可引用已连接节点的变量")
                    : tx("输入简短描述…")))
                : busy
                  ? tx("优化任务执行中…")
                  : tx("点击 ✨ 生成优化提示词，也可在此直接编辑")
            }
            value={displayText}
            readOnly={busy && tab === "optimized"}
            onChange={(e) => {
              if (busy) return;
              const text = e.target.value;
              if (tab === "raw") {
                onChange({ ...value, raw: text });
                // 刚输入 "/" 且有可用变量时弹出补全
                const pos = e.target.selectionStart ?? text.length;
                if (variables?.length && text[pos - 1] === "/") {
                  setMenuAt(pos - 1);
                  setActiveIndex(0);
                } else if (menuAt != null && pos <= menuAt) {
                  setMenuAt(null);
                }
              } else {
                onChange({ ...value, optimized: text });
              }
            }}
            onKeyDown={(e) => {
              if (menuAt == null || !variables?.length) return;
              if (e.key === "Escape") {
                setMenuAt(null);
              } else if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) => (i + 1) % variables.length);
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) => (i - 1 + variables.length) % variables.length);
              } else if (e.key === "Enter") {
                e.preventDefault();
                const v = variables[activeIndex];
                if (v) insertVar(v);
              }
            }}
            onBlur={() => window.setTimeout(() => setMenuAt(null), 150)}
          />
          {menuAt != null && variables && variables.length > 0 && (
            <div className="absolute left-0 top-full z-40 mt-1 w-56 rounded-xl border border-border bg-card p-1 shadow-lg">
              <div className="px-2 py-1 text-[10px] text-muted-foreground">{tx("插入变量")}</div>
              {variables.map((v, index) => (
                <button
                  key={v.name}
                  type="button"
                  className={cn(
                    "flex w-full flex-col rounded-md px-2 py-1 text-left",
                    index === activeIndex ? "bg-muted" : "hover:bg-muted",
                  )}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    insertVar(v);
                  }}
                >
                  <span className="text-sm text-primary">{v.tag ?? `{{${v.name}}}`}</span>
                  <span className="truncate text-[10px] text-muted-foreground">
                    {v.name} · {v.preview}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {statusMsg && (
          <p
            className={cn(
              "text-xs",
              job?.status === "failed" ||
                job?.status === "canceled" ||
                /失败|错误|尚未|取消|fail|error|cancel/i.test(statusMsg)
                ? "text-danger"
                : "text-muted-foreground",
            )}
          >
            {statusMsg}
            {running && job && !TERMINAL_STATUSES.includes(job.status)
              ? `（${Math.round((job.progress ?? 0) * 100)}%）`
              : ""}
          </p>
        )}
        {stale && !busy && (
          <p className="text-xs text-warning">
            {tx("原始输入已变更，优化稿可能过期。点击 ✨ 重新生成覆盖，或关闭下方开关使用原始输入。")}
          </p>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={value.useOptimized}
            disabled={!value.optimized.trim() || busy}
            onChange={(e) => onChange({ ...value, useOptimized: e.target.checked })}
          />
          {tx("使用优化后提示词执行任务")}
        </label>
      </div>
    </Field>
  );
}

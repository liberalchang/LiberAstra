/** 提示词模板库:功能模板(task)与场景预设(scene)的增删改。
 *
 * 合并机制是「内置为底、用户覆盖」:保存=写覆盖层(与内置一致则保持默认),
 * 内置覆盖可恢复默认,用户自建条目可删除。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, RotateCcw, Save, ScrollText, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import {
  api,
  type PromptOrigin,
  type PromptSceneOut,
  type PromptTaskOut,
} from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field, areaClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { LightboxShell } from "@/components/ui/lightbox";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";
import { hasTemplateIdConflict } from "@/lib/promptTemplates";
import { cn } from "@/lib/utils";

/** task capability → 使用它的功能页(帮用户理解改动影响面) */
const CAP_LABELS: Record<string, string> = {
  t2i: "文生图",
  i2i: "图生图/编辑",
  upscale: "修复放大",
  i2v: "图生视频",
  t2v: "文生视频",
  quick_visual: "快速创作画面",
  motion: "动作迁移",
  quick_topic: "快速创作主题",
  assets_topic: "自定义素材主题",
  character_sheet: "角色外观",
};

interface TaskDraft {
  id: string;
  name: string;
  capabilities: string;
  system: string;
}

interface SceneDraft {
  id: string;
  name: string;
  append: string;
}

const emptyTask: TaskDraft = { id: "", name: "", capabilities: "", system: "" };
const emptyScene: SceneDraft = { id: "", name: "", append: "" };

type ConfirmAction = {
  kind: "task" | "scene";
  mode: "reset" | "delete";
  id: string;
  name: string;
};

const capsKey = (caps: string[] | undefined) =>
  (caps ?? [])
    .map((cap) => cap.trim())
    .filter(Boolean)
    .sort()
    .join(",");

const draftCapsKey = (value: string) =>
  value
    .split(",")
    .map((cap) => cap.trim())
    .filter(Boolean)
    .sort()
    .join(",");

const originOf = (item: { custom?: boolean; origin?: PromptOrigin } | undefined) =>
  item?.origin ?? (item?.custom ? "customized" : "builtin");

export function PromptsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"tasks" | "scenes">("tasks");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [taskDraft, setTaskDraft] = useState<TaskDraft>(emptyTask);
  const [sceneDraft, setSceneDraft] = useState<SceneDraft>(emptyScene);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);

  const { data } = useQuery({ queryKey: ["prompts-catalog"], queryFn: api.listPrompts });
  const tasks = data?.tasks ?? [];
  const scenes = data?.scenes ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["prompts-catalog"] });

  const selectTask = (t: PromptTaskOut) => {
    setIsNew(false);
    setSelectedId(t.id);
    setTaskDraft({
      id: t.id,
      name: t.name,
      capabilities: (t.capabilities ?? []).join(","),
      system: t.system,
    });
    setNotice(null);
    setError(null);
  };
  const selectScene = (s: PromptSceneOut) => {
    setIsNew(false);
    setSelectedId(s.id);
    setSceneDraft({ id: s.id, name: s.name, append: s.append });
    setNotice(null);
    setError(null);
  };
  const changeTab = (next: "tasks" | "scenes") => {
    setSelectedId(null);
    setTab(next);
  };

  useEffect(() => {
    if (!data || isNew || selectedId !== null) return;
    if (tab === "tasks") {
      const first = data.tasks[0];
      if (!first) return;
      setSelectedId(first.id);
      setTaskDraft({
        id: first.id,
        name: first.name,
        capabilities: (first.capabilities ?? []).join(","),
        system: first.system,
      });
      return;
    }
    const first = data.scenes[0];
    if (!first) return;
    setSelectedId(first.id);
    setSceneDraft({ id: first.id, name: first.name, append: first.append });
  }, [data, tab, isNew, selectedId]);

  const saveTask = useMutation({
    mutationFn: () =>
      api.putPromptTask(taskDraft.id.trim(), {
        name: taskDraft.name.trim(),
        system: taskDraft.system,
        capabilities: taskDraft.capabilities
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
      }),
    onSuccess: (result) => {
      setNotice(
        result.origin === "builtin"
          ? tx("模板已保存（与默认一致）")
          : tx("模板已保存"),
      );
      setError(null);
      setIsNew(false);
      setSelectedId(taskDraft.id.trim());
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
    },
  });
  const saveScene = useMutation({
    mutationFn: () =>
      api.putPromptScene(sceneDraft.id.trim(), {
        name: sceneDraft.name.trim(),
        append: sceneDraft.append,
      }),
    onSuccess: (result) => {
      setNotice(
        result.origin === "builtin"
          ? tx("模板已保存（与默认一致）")
          : tx("模板已保存"),
      );
      setError(null);
      setIsNew(false);
      setSelectedId(sceneDraft.id.trim());
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
    },
  });

  const resetTask = useMutation({
    mutationFn: async (id: string) => {
      await api.deletePromptTask(id, "reset");
      return { id, catalog: await api.listPrompts() };
    },
    onSuccess: ({ id, catalog }) => {
      queryClient.setQueryData(["prompts-catalog"], catalog);
      const restored = catalog.tasks.find((item) => item.id === id);
      if (restored) {
        setTaskDraft({
          id: restored.id,
          name: restored.name,
          capabilities: restored.capabilities.join(","),
          system: restored.system,
        });
      }
      setNotice(tx("已恢复默认"));
      setError(null);
      setConfirmAction(null);
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
      setConfirmAction(null);
    },
  });
  const resetScene = useMutation({
    mutationFn: async (id: string) => {
      await api.deletePromptScene(id, "reset");
      return { id, catalog: await api.listPrompts() };
    },
    onSuccess: ({ id, catalog }) => {
      queryClient.setQueryData(["prompts-catalog"], catalog);
      const restored = catalog.scenes.find((item) => item.id === id);
      if (restored) {
        setSceneDraft({
          id: restored.id,
          name: restored.name,
          append: restored.append,
        });
      }
      setNotice(tx("已恢复默认"));
      setError(null);
      setConfirmAction(null);
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
      setConfirmAction(null);
    },
  });
  const deleteTask = useMutation({
    mutationFn: (id: string) => api.deletePromptTask(id, "delete"),
    onSuccess: () => {
      setNotice(tx("已删除"));
      setError(null);
      setSelectedId(null);
      setConfirmAction(null);
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
      setConfirmAction(null);
    },
  });
  const deleteScene = useMutation({
    mutationFn: (id: string) => api.deletePromptScene(id, "delete"),
    onSuccess: () => {
      setNotice(tx("已删除"));
      setError(null);
      setSelectedId(null);
      setConfirmAction(null);
      void invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
      setConfirmAction(null);
    },
  });

  const importMut = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(importText) as Record<string, unknown>;
      return api.importPrompts(parsed);
    },
    onSuccess: (r) => {
      setImportOpen(false);
      setImportText("");
      setNotice(tx("已导入 {t} 个功能模板、{s} 个场景预设", { t: r.tasks, s: r.scenes }));
      void invalidate();
    },
    onError: (err) => setError(err.message),
  });

  const exportCatalog = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "prompts-catalog.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const currentTask = tasks.find((t) => t.id === selectedId);
  const currentScene = scenes.find((s) => s.id === selectedId);
  const list = tab === "tasks" ? tasks : scenes;
  const taskOrigin = originOf(currentTask);
  const sceneOrigin = originOf(currentScene);
  const taskIdConflict =
    isNew && hasTemplateIdConflict(taskDraft.id, tasks.map((t) => t.id));
  const sceneIdConflict =
    isNew && hasTemplateIdConflict(sceneDraft.id, scenes.map((s) => s.id));
  const taskDirty = isNew
    ? Boolean(
        taskDraft.id.trim() ||
          taskDraft.name.trim() ||
          taskDraft.system.trim() ||
          taskDraft.capabilities.trim(),
      )
    : Boolean(
        currentTask &&
          (taskDraft.name !== currentTask.name ||
            taskDraft.system !== currentTask.system ||
            draftCapsKey(taskDraft.capabilities) !== capsKey(currentTask.capabilities)),
      );
  const sceneDirty = isNew
    ? Boolean(sceneDraft.id.trim() || sceneDraft.name.trim() || sceneDraft.append.trim())
    : Boolean(
        currentScene &&
          (sceneDraft.name !== currentScene.name || sceneDraft.append !== currentScene.append),
      );
  const confirmBusy =
    confirmAction?.kind === "task"
      ? confirmAction.mode === "reset"
        ? resetTask.isPending
        : deleteTask.isPending
      : confirmAction?.mode === "reset"
        ? resetScene.isPending
        : deleteScene.isPending;

  const runConfirm = () => {
    if (!confirmAction) return;
    if (confirmAction.kind === "task") {
      if (confirmAction.mode === "reset") resetTask.mutate(confirmAction.id);
      else deleteTask.mutate(confirmAction.id);
      return;
    }
    if (confirmAction.mode === "reset") resetScene.mutate(confirmAction.id);
    else deleteScene.mutate(confirmAction.id);
  };

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader
        kind="prompts"
        icon={ScrollText}
        title={tx("提示词模板")}
        description={tx("管理 ✨ 提示词优化的功能模板与场景预设；保存后立即对下次优化生效。")}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          value={tab}
          onChange={changeTab}
          ariaLabel={tx("模板类型")}
          options={[
            { value: "tasks", label: tx("功能模板") },
            { value: "scenes", label: tx("场景预设") },
          ]}
        />
        <div className="ml-auto flex gap-1">
          <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
            <Upload /> {tx("导入")}
          </Button>
          <Button variant="outline" size="sm" onClick={exportCatalog}>
            <Download /> {tx("导出")}
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setIsNew(true);
              setSelectedId(null);
              setTaskDraft(emptyTask);
              setSceneDraft(emptyScene);
            }}
          >
            <Plus /> {tx("新建")}
          </Button>
        </div>
      </div>

      {(notice || error) && (
        <p className={cn("text-sm", error ? "text-danger" : "text-success")} role="status">
          {error ?? notice}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-[240px_1fr]">
        {/* 条目列表 */}
        <div className="flex flex-col gap-1">
          {list.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => (tab === "tasks" ? selectTask(item as PromptTaskOut) : selectScene(item as PromptSceneOut))}
              className={cn(
                "flex items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-left text-sm hover:bg-muted",
                selectedId === item.id && !isNew && "border-border bg-card font-medium",
              )}
            >
              <span className="min-w-0 flex-1 truncate">{item.name}</span>
              {(item.origin === "user" || item.custom) && (
                <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
                  {item.origin === "user"
                    ? tx(tab === "tasks" ? "我的模板" : "我的预设")
                    : tx("已自定义")}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* 编辑区 */}
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            {tab === "tasks" ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label={tx("模板 ID")}
                    hint={
                      isNew
                        ? taskIdConflict
                          ? tx("ID 已被现有模板使用；请换一个唯一 ID。要修改内置模板，请先在左侧选中它。")
                          : tx("新建后不可改；请使用唯一 ID。要修改内置模板，请先在左侧选中它。")
                        : undefined
                    }
                  >
                    <Input
                      value={taskDraft.id}
                      disabled={!isNew}
                      onChange={(e) => setTaskDraft({ ...taskDraft, id: e.target.value })}
                      placeholder="t2i"
                    />
                  </Field>
                  <Field label={tx("名称")}>
                    <Input
                      value={taskDraft.name}
                      onChange={(e) => setTaskDraft({ ...taskDraft, name: e.target.value })}
                    />
                  </Field>
                </div>
                <Field
                  label={tx("适用功能")}
                  hint={tx("逗号分隔的 capability;留空表示不参与页面匹配。当前可选:") + Object.keys(CAP_LABELS).join(" / ")}
                >
                  <Input
                    value={taskDraft.capabilities}
                    onChange={(e) => setTaskDraft({ ...taskDraft, capabilities: e.target.value })}
                    placeholder="t2i"
                  />
                </Field>
                {currentTask && currentTask.capabilities.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {tx("使用它的页面:")}
                    {currentTask.capabilities.map((c) => tx(CAP_LABELS[c] ?? c)).join("、")}
                  </p>
                )}
                <Field label={tx("系统提示词")} hint={tx("优化器按此模板扩写用户输入;保存后对下次优化立即生效。")}>
                  <textarea
                    className={`${areaClass} min-h-48 font-mono text-xs`}
                    value={taskDraft.system}
                    onChange={(e) => setTaskDraft({ ...taskDraft, system: e.target.value })}
                  />
                </Field>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={
                      !taskDraft.id.trim() ||
                      !taskDraft.name.trim() ||
                      !taskDraft.system.trim() ||
                      !taskDirty ||
                      taskIdConflict ||
                      saveTask.isPending
                    }
                    onClick={() => saveTask.mutate()}
                  >
                    <Save /> {saveTask.isPending ? tx("保存中…") : tx("保存")}
                  </Button>
                  {!isNew && taskOrigin === "customized" && currentTask && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={resetTask.isPending}
                      onClick={() =>
                        setConfirmAction({
                          kind: "task",
                          mode: "reset",
                          id: currentTask.id,
                          name: currentTask.name,
                        })
                      }
                    >
                      <RotateCcw /> {tx("恢复默认")}
                    </Button>
                  )}
                  {!isNew && taskOrigin === "user" && currentTask && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={deleteTask.isPending}
                      onClick={() =>
                        setConfirmAction({
                          kind: "task",
                          mode: "delete",
                          id: currentTask.id,
                          name: currentTask.name,
                        })
                      }
                    >
                      <Trash2 /> {tx("删除")}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label={tx("预设 ID")}
                    hint={
                      isNew
                        ? sceneIdConflict
                          ? tx("ID 已被现有模板使用；请换一个唯一 ID。要修改内置模板，请先在左侧选中它。")
                          : tx("新建后不可改；请使用唯一 ID。要修改内置模板，请先在左侧选中它。")
                        : undefined
                    }
                  >
                    <Input
                      value={sceneDraft.id}
                      disabled={!isNew}
                      onChange={(e) => setSceneDraft({ ...sceneDraft, id: e.target.value })}
                      placeholder="photo"
                    />
                  </Field>
                  <Field label={tx("名称")}>
                    <Input
                      value={sceneDraft.name}
                      onChange={(e) => setSceneDraft({ ...sceneDraft, name: e.target.value })}
                    />
                  </Field>
                </div>
                <Field label={tx("叠加文本")} hint={tx("叠加在功能模板之上的风格倾向;「自动」预设留空表示不强制场景。")}>
                  <textarea
                    className={`${areaClass} min-h-32 font-mono text-xs`}
                    value={sceneDraft.append}
                    onChange={(e) => setSceneDraft({ ...sceneDraft, append: e.target.value })}
                  />
                </Field>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={
                      !sceneDraft.id.trim() ||
                      !sceneDraft.name.trim() ||
                      !sceneDirty ||
                      sceneIdConflict ||
                      saveScene.isPending
                    }
                    onClick={() => saveScene.mutate()}
                  >
                    <Save /> {saveScene.isPending ? tx("保存中…") : tx("保存")}
                  </Button>
                  {!isNew && sceneOrigin === "customized" && currentScene && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={resetScene.isPending}
                      onClick={() =>
                        setConfirmAction({
                          kind: "scene",
                          mode: "reset",
                          id: currentScene.id,
                          name: currentScene.name,
                        })
                      }
                    >
                      <RotateCcw /> {tx("恢复默认")}
                    </Button>
                  )}
                  {!isNew && sceneOrigin === "user" && currentScene && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={deleteScene.isPending}
                      onClick={() =>
                        setConfirmAction({
                          kind: "scene",
                          mode: "delete",
                          id: currentScene.id,
                          name: currentScene.name,
                        })
                      }
                    >
                      <Trash2 /> {tx("删除")}
                    </Button>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {importOpen && (
        <LightboxShell onClose={() => setImportOpen(false)} ariaLabel={tx("导入模板")} className="max-w-lg">
          <div className="flex flex-col gap-3 p-4">
            <p className="text-sm font-medium">{tx("导入提示词模板")}</p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {tx('粘贴 { "tasks": {...} } 或 { "scenes": {...} } 结构的 JSON;同名条目覆盖为自定义，与内置一致时保持默认。')}
            </p>
            <textarea
              className={`${areaClass} min-h-32 font-mono text-xs`}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{"tasks": {"t2i": {"name": "…", "system": "…"}}}'
            />
            <div className="flex gap-2">
              <Button size="sm" disabled={!importText.trim() || importMut.isPending} onClick={() => importMut.mutate()}>
                {importMut.isPending ? tx("导入中…") : tx("导入")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setImportOpen(false)}>
                {tx("取消")}
              </Button>
            </div>
          </div>
        </LightboxShell>
      )}

      {confirmAction && (
        <ConfirmDialog
          title={
            confirmAction.mode === "delete"
              ? tx("删除「{name}」？", { name: confirmAction.name })
              : tx("恢复默认「{name}」？", { name: confirmAction.name })
          }
          message={
            confirmAction.mode === "delete"
              ? tx("删除后无法恢复；只影响用户创建的模板，内置模板不会被删除。")
              : tx("将删除你对这个模板的修改，恢复为内置内容。")
          }
          confirmLabel={
            confirmAction.mode === "delete" ? tx("删除") : tx("恢复默认")
          }
          danger={confirmAction.mode === "delete"}
          busy={confirmBusy}
          onConfirm={runConfirm}
          onClose={() => setConfirmAction(null)}
        />
      )}
    </div>
  );
}

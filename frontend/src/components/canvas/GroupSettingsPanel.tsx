/** 工作流包分组（所属）管理面板：嵌入「设置 → 工作流包」页的分组 tab。
 * 数据即 key(组名): value(包名列表),整体保存在服务端 app_settings。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type CanvasGroups } from "@/api/client";
import { Button } from "@/components/ui/button";
import { selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

/** capability → 默认组名（与后端 DEFAULT_GROUP_NAMES 一致；删组后包回落到这里）。 */
export const CAPABILITY_GROUP: Record<string, string> = {
  t2i: "文生图",
  i2i: "图生图",
  upscale: "放大修复",
  t2v: "文生视频",
  i2v: "图生视频",
  avatar: "数字人",
  motion: "动作迁移",
  analysis: "画面分析",
};

export function GroupSettingsPanel() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"assign" | "manage">("assign");
  const [draft, setDraft] = useState<CanvasGroups | null>(null);
  const [newGroup, setNewGroup] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameTo, setRenameTo] = useState("");

  const { data: groups } = useQuery({ queryKey: ["canvas-groups"], queryFn: api.getCanvasGroups });
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  // 初次载入时复制一份可编辑草稿
  useEffect(() => {
    if (groups && draft === null) setDraft(structuredClone(groups));
  }, [groups, draft]);

  const save = useMutation({
    mutationFn: (body: CanvasGroups) => api.putCanvasGroups(body),
    onSuccess: (saved) => {
      setDraft(structuredClone(saved));
      void queryClient.invalidateQueries({ queryKey: ["canvas-groups"] });
    },
  });

  if (!draft) return null;
  const groupNames = Object.keys(draft);
  const dirty = JSON.stringify(draft) !== JSON.stringify(groups ?? {});

  /** 包当前所属组（不在任何组里 = 未分组）。 */
  const groupOf = (packName: string) =>
    groupNames.find((g) => draft[g].includes(packName)) ?? "";

  const assign = (packName: string, group: string) => {
    const next: CanvasGroups = Object.fromEntries(
      Object.entries(draft).map(([g, list]) => [g, list.filter((p) => p !== packName)]),
    );
    if (group) next[group] = [...(next[group] ?? []), packName];
    setDraft(next);
  };

  const addGroup = () => {
    const name = newGroup.trim();
    if (!name || draft[name]) return;
    setDraft({ ...draft, [name]: [] });
    setNewGroup("");
  };

  const deleteGroup = (name: string) => {
    // 组里的包回落到 capability 默认组（不存在则顺带创建）
    const orphans = draft[name] ?? [];
    const next: CanvasGroups = { ...draft };
    delete next[name];
    for (const packName of orphans) {
      const cap = packs?.find((p) => p.name === packName)?.capability ?? "";
      const fallback = CAPABILITY_GROUP[cap] ?? cap;
      if (fallback === name) continue;
      if (fallback) next[fallback] = [...(next[fallback] ?? []), packName];
    }
    setDraft(next);
  };

  const commitRename = () => {
    if (!renaming) return;
    const target = renameTo.trim();
    if (target && target !== renaming && !draft[target]) {
      const next: CanvasGroups = {};
      for (const [g, list] of Object.entries(draft)) {
        next[g === renaming ? target : g] = list;
      }
      setDraft(next);
    }
    setRenaming(null);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Segmented
          ariaLabel={tx("分组设置")}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
          options={[
            { value: "assign", label: tx("添加工作流包") },
            { value: "manage", label: tx("分组管理") },
          ]}
        />
        <span className="text-xs text-muted-foreground">
          {tx("分组即画布功能节点里的「所属」：选中一个组 = 选定这批工作流包")}
        </span>
        <Button
          size="sm"
          className="ml-auto"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate(draft)}
        >
          {tx("保存")}
        </Button>
      </div>

      {tab === "assign" ? (
        <div className="flex flex-col gap-1.5">
          {(packs ?? []).map((pack) => (
            <div
              key={pack.name}
              className="flex items-center gap-3 rounded-lg border border-border px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{pack.name}</div>
                <div className="text-[10px] text-muted-foreground">
                  {tx(CAPABILITY_GROUP[pack.capability] ?? pack.capability)}
                  {pack.description ? ` · ${pack.description}` : ""}
                </div>
              </div>
              <select
                className={selectClass}
                style={{ width: "9rem", flexShrink: 0 }}
                value={groupOf(pack.name)}
                onChange={(e) => assign(pack.name, e.target.value)}
              >
                <option value="">{tx("未分组")}</option>
                {groupNames.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {groupNames.map((g) => (
            <div key={g} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
              {renaming === g ? (
                <>
                  <Input
                    className="h-7 flex-1 text-sm"
                    value={renameTo}
                    onChange={(e) => setRenameTo(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && commitRename()}
                    autoFocus
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={commitRename}
                    aria-label={tx("确认")}
                  >
                    <Check className="size-3.5" />
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm">{g}</span>
                  <span className="text-xs text-muted-foreground">
                    {tx("{n} 个包", { n: draft[g].length })}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    title={tx("重命名")}
                    onClick={() => {
                      setRenaming(g);
                      setRenameTo(g);
                    }}
                  >
                    <Pencil className="size-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 text-danger"
                    title={tx("删除分组（包回落到默认组）")}
                    onClick={() => deleteGroup(g)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </>
              )}
            </div>
          ))}
          <div className="mt-2 flex gap-2">
            <Input
              className="h-8 flex-1 text-sm"
              placeholder={tx("新分组名")}
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addGroup()}
            />
            <Button variant="outline" size="sm" onClick={addGroup} disabled={!newGroup.trim()}>
              <Plus className="size-4" />
              {tx("新增分组")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/** 画布主页的菜单设置：语音 / 图像 / 视频三类功能简称。
 * CanvasListPage 引用。读写 /api/v1/canvases/menu。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Image as ImageIcon, Mic, Pencil, Trash2, Video } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type CanvasMenuItem, type ExecutionSpec } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";

const CATEGORIES = [
  ["speech", "语音"],
  ["image", "图像"],
  ["video", "视频"],
] as const;

export function CanvasMenuSettings() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const { data: specs } = useQuery({ queryKey: ["execution-specs"], queryFn: () => api.executionSpecs() });
  const [items, setItems] = useState<CanvasMenuItem[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    if (data) setItems(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (next: CanvasMenuItem[]) => api.saveCanvasMenu(next),
    onSuccess: (saved) => {
      setItems(saved);
      setMessage(null);
      void queryClient.invalidateQueries({ queryKey: ["canvas-menu"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const update = (id: string, patch: Partial<CanvasMenuItem>) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const commit = (next: CanvasMenuItem[]) => {
    setItems(next);
    save.mutate(next);
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        {tx("自动匹配使用已启用且具备该能力的模型和工作流，属性里仍可改选。手动指定后，属性里只列出勾选的项。默认是新节点最初选中的那一个。完成编辑后即保存。")}
      </p>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      {CATEGORIES.map(([category, label]) => (
        <section key={category} className="flex flex-col gap-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium">{tx(label)}</h2>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const id = `custom_${category}_${Date.now().toString(36)}`;
                setItems((current) => [
                  ...current,
                  {
                    id,
                    category,
                    title: "新功能",
                    hint: "",
                    sub_capability: category === "speech" ? "tts" : category === "image" ? "t2i" : "t2v",
                    bind_mode: "auto",
                    manual_targets: [],
                    default_target: null,
                    enabled: true,
                  },
                ]);
                setEditingId(id);
              }}
            >
              {tx("添加功能")}
            </Button>
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-3">
            {items
              .filter((item) => item.category === category)
              .map((item) =>
                editingId === item.id ? (
                  <div key={item.id} className="col-span-full">
                    <MenuCard
                      item={item}
                      specs={specs ?? []}
                      onChange={(patch) => update(item.id, patch)}
                      onRemove={() => {
                        commit(items.filter((row) => row.id !== item.id));
                        setEditingId(null);
                      }}
                    />
                    <Button className="mt-2" size="sm" variant="outline" disabled={save.isPending} onClick={() => save.mutate(items, { onSuccess: () => setEditingId(null) })}>
                      {save.isPending ? tx("保存中…") : tx("完成编辑")}
                    </Button>
                  </div>
                ) : (
                  <SummaryCard
                    key={item.id}
                    item={item}
                    specs={specs ?? []}
                    onEdit={() => setEditingId(item.id)}
                    onToggle={() => commit(items.map((row) => (row.id === item.id ? { ...row, enabled: row.enabled === false } : row)))}
                    onRemove={() => commit(items.filter((row) => row.id !== item.id))}
                  />
                ),
              )}
          </div>
        </section>
      ))}
    </div>
  );
}

const ABILITIES = [
  ["tts", "文字转语音"],
  ["asr", "语音识别"],
  ["t2i", "文生图"],
  ["i2i_single", "单图编辑"],
  ["i2i_multi", "多图编辑"],
  ["outfit_swap", "换衣"],
  ["depth_pose", "深度换姿"],
  ["depth_gen", "深度生图"],
  ["color_grade", "调色"],
  ["inpaint", "蒙版"],
  ["upscale", "放大修复"],
  ["analysis", "画面分析"],
  ["t2v", "文生视频"],
  ["t2v_enhance", "文生增强"],
  ["i2v_first", "图生视频"],
  ["i2v_flf", "首尾帧视频"],
  ["v2v_ref", "参考视频"],
  ["i2v_orbit", "360全景"],
  ["i2v_enhance", "图生增强"],
  ["avatar", "数字人口播"],
  ["motion", "动作迁移"],
  ["video_analysis", "视频分析"],
] as const;

function SummaryCard({
  item,
  specs,
  onEdit,
  onToggle,
  onRemove,
}: {
  item: CanvasMenuItem;
  specs: ExecutionSpec[];
  onEdit: () => void;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const tx = useTx();
  const ability = ABILITIES.find(([id]) => id === item.sub_capability)?.[1] ?? item.sub_capability;
  const Icon = item.category === "speech" ? Mic : item.category === "video" ? Video : ImageIcon;
  const description = item.hint && item.hint !== item.title && item.hint !== ability ? item.hint : "";
  const same = (spec: ExecutionSpec) =>
    Boolean(
      item.default_target &&
        spec.sub_capability === item.sub_capability &&
        spec.target_id === item.default_target.target_id &&
        spec.target_type === item.default_target.target_type &&
        (item.default_target.provider_id == null || item.default_target.provider_id === spec.provider_id),
    );
  const defaultName = specs.find(same)?.display_name;
  const on = item.enabled !== false;
  const binding =
    item.bind_mode === "manual"
      ? defaultName
        ? tx("手动指定 · 默认 {name}", { name: defaultName })
        : tx("手动指定")
      : defaultName
        ? tx("自动匹配 · 默认 {name}", { name: defaultName })
        : tx("自动匹配");
  return (
    <article className={`flex gap-3 rounded-2xl border border-border bg-card p-4 ${on ? "" : "text-muted-foreground"}`}>
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
        {item.sub_capability === "tts" || item.sub_capability === "asr" ? <AudioLines className="size-4" /> : <Icon className="size-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-medium">{item.title}</h3>
        {ability !== item.title ? <p className="mt-0.5 text-xs text-muted-foreground">{tx(ability)}</p> : null}
        {description ? <p className="mt-2 line-clamp-2 text-sm">{description}</p> : null}
        <p className="mt-3 line-clamp-2 text-xs text-muted-foreground">{binding}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        <button
          type="button"
          role="switch"
          aria-label={tx("启用 {name}", { name: item.title })}
          aria-checked={on}
          className={`relative h-5 w-9 rounded-full ${on ? "bg-primary" : "bg-muted"}`}
          onClick={onToggle}
        >
          <span className={`absolute top-0.5 size-4 rounded-full bg-card ${on ? "left-4" : "left-0.5"}`} />
        </button>
        <button type="button" className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={tx("编辑")} onClick={onEdit}>
          <Pencil className="size-4" />
        </button>
        <button type="button" className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={tx("删除")} onClick={onRemove}>
          <Trash2 className="size-4" />
        </button>
      </div>
    </article>
  );
}

function MenuCard({
  item,
  specs,
  onChange,
  onRemove,
}: {
  item: CanvasMenuItem;
  specs: ExecutionSpec[];
  onChange: (patch: Partial<CanvasMenuItem>) => void;
  onRemove: () => void;
}) {
  const tx = useTx();
  const options = specs.filter((spec) => spec.sub_capability === item.sub_capability);
  const same = (spec: ExecutionSpec, target: { provider_id?: number | null; target_type: string; target_id: string }) =>
    target.target_type === spec.target_type &&
    target.target_id === spec.target_id &&
    (target.provider_id == null || target.provider_id === spec.provider_id);
  const picked = options.filter((spec) => item.manual_targets.some((target) => same(spec, target)));
  const defaultPool = item.bind_mode === "manual" ? picked : options;
  const current = item.default_target
    ? defaultPool.find((spec) => same(spec, item.default_target!))
    : undefined;
  const toggleTarget = (spec: ExecutionSpec) => {
    const exists = item.manual_targets.some((target) => same(spec, target));
    const manual_targets = exists
      ? item.manual_targets.filter((target) => !same(spec, target))
      : [
          ...item.manual_targets,
          { provider_id: spec.provider_id, target_type: spec.target_type, target_id: spec.target_id },
        ];
    const default_target =
      exists && item.default_target && same(spec, item.default_target) ? null : item.default_target;
    onChange({ manual_targets, default_target, bind_mode: "manual" });
  };
  const markDefault = (spec: ExecutionSpec | null) => {
    onChange({
      default_target: spec
        ? { provider_id: spec.provider_id, target_type: spec.target_type, target_id: spec.target_id }
        : null,
    });
  };
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-border bg-background p-4">
      <div className="flex items-start justify-between gap-2">
        <Input value={item.title} maxLength={10} aria-label={tx("简称")} onChange={(event) => onChange({ title: event.target.value })} />
        <Button variant="ghost" size="sm" onClick={onRemove}>{tx("删除")}</Button>
      </div>
      <Field label={tx("能力")}>
        <select
          className={selectClass}
          value={item.sub_capability}
          onChange={(event) => onChange({ sub_capability: event.target.value, manual_targets: [], default_target: null })}
        >
          {ABILITIES.map(([id, label]) => (
            <option key={id} value={id}>{tx(label)}</option>
          ))}
        </select>
      </Field>
      <Field label={tx("说明")}>
        <Input value={item.hint} onChange={(event) => onChange({ hint: event.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1 text-sm">
        <button
          type="button"
          className={item.bind_mode !== "manual" ? "rounded-md bg-background py-1.5" : "py-1.5 text-muted-foreground"}
          onClick={() => onChange({ bind_mode: "auto" })}
        >
          {tx("自动匹配")}
        </button>
        <button
          type="button"
          className={item.bind_mode === "manual" ? "rounded-md bg-background py-1.5" : "py-1.5 text-muted-foreground"}
          onClick={() => onChange({ bind_mode: "manual" })}
        >
          {tx("手动指定")}
        </button>
      </div>
      {item.bind_mode !== "manual" ? (
        <Field label={tx("新建节点时的默认项")}>
          <select
            className={selectClass}
            value={current ? `${current.provider_id ?? "x"}:${current.target_type}:${current.target_id}` : ""}
            onChange={(event) => {
              const spec = options.find((row) => `${row.provider_id ?? "x"}:${row.target_type}:${row.target_id}` === event.target.value);
              markDefault(spec ?? null);
            }}
          >
            <option value="">{tx("第一个匹配项")}</option>
            {options.map((spec) => (
              <option key={`${spec.provider_id ?? "x"}:${spec.target_type}:${spec.target_id}`} value={`${spec.provider_id ?? "x"}:${spec.target_type}:${spec.target_id}`}>
                {(spec.provider_name || spec.provider_type) + " / " + spec.display_name}
              </option>
            ))}
          </select>
        </Field>
      ) : options.length === 0 ? (
        <p className="text-sm text-muted-foreground">{tx("还没有具备这个能力的工作流或已启用模型")}</p>
      ) : (
        <ul className="flex max-h-64 flex-col gap-2 overflow-auto">
          {options.map((spec) => {
            const checked = item.manual_targets.some((target) => same(spec, target));
            const isDefault = Boolean(current && same(spec, { provider_id: current.provider_id, target_type: current.target_type, target_id: current.target_id }));
            return (
              <li key={`${spec.provider_id ?? "x"}:${spec.target_type}:${spec.target_id}`} className="flex items-center gap-2 rounded-lg border border-border px-2 py-2">
                <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
                  <input type="checkbox" checked={checked} onChange={() => toggleTarget(spec)} />
                  <span className="min-w-0">
                    <span className="block truncate">{spec.display_name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{spec.provider_name || spec.provider_type}</span>
                  </span>
                </label>
                <button
                  type="button"
                  disabled={!checked}
                  className={isDefault ? "shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground" : "shrink-0 rounded-full border border-border px-2 py-0.5 text-xs disabled:opacity-40"}
                  onClick={() => markDefault(isDefault ? null : spec)}
                >
                  {tx("默认")}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

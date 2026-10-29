/** 自定义菜单节点的属性：只列出该功能允许的服务商和模型。
 * NodeInspector 在节点带 presetId 时渲染。
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api, type ExecutionSpec } from "@/api/client";
import { applyMenuToNode, providerForSpec, resolveSpec, specsForMenu } from "@/canvas/applyMenu";
import type { CanvasFlowNode, FunctionNodeData } from "@/canvas/types";
import { Field, selectClass } from "@/components/ui/field";
import { useTx } from "@/i18n/tx";

export function PresetInspector({
  node,
  onFlash,
}: {
  node: CanvasFlowNode;
  onFlash: (text: string, opts?: { sticky?: boolean }) => void;
}) {
  const tx = useTx();
  const d = node.data as FunctionNodeData;
  const { data: menu } = useQuery({ queryKey: ["canvas-menu"], queryFn: api.getCanvasMenu });
  const { data: specs } = useQuery({ queryKey: ["execution-specs"], queryFn: () => api.executionSpecs() });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows(), staleTime: 60_000 });
  const item = (menu ?? []).find((row) => row.id === d.presetId);
  const pool = item ? specsForMenu(item, specs ?? []) : [];
  const providerIds = [
    ...new Set(pool.map((spec) => providerForSpec(spec, providers ?? [])?.id).filter((id): id is number => id != null)),
  ];

  const apply = (spec: ExecutionSpec | undefined, source = item) => {
    if (!source) return;
    const chosen = spec ?? resolveSpec(source, specs ?? []);
    const created = applyMenuToNode(
      node.id,
      {
        ...source,
        default_target: chosen
          ? { provider_id: chosen.provider_id, target_type: chosen.target_type, target_id: chosen.target_id }
          : source.default_target,
      },
      chosen,
      providers ?? [],
      packs ?? [],
    );
    if (created > 0) onFlash(tx("已补建 {n} 个输入节点", { n: created }));
  };

  const defaultKey = item?.default_target
    ? `${item.default_target.provider_id ?? ""}:${item.default_target.target_type}:${item.default_target.target_id}`
    : "";
  // 还没绑定时用菜单默认项。当前模型不在允许范围内（例如改成了手动指定）时也改到默认项。
  useEffect(() => {
    if (!item || !specs?.length) return;
    const inPool = pool.some((row) => row.target_id === d.targetId && row.target_type === d.targetType);
    if (d.targetId && inPool) return;
    const chosen = resolveSpec(item, specs);
    if (!chosen || (chosen.target_id === d.targetId && chosen.target_type === d.targetType)) return;
    apply(chosen);
    // apply 每次渲染都是新函数
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.id, item?.bind_mode, defaultKey, specs, d.targetId, d.targetType, pool]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium">{d.presetTitle || item?.title}</p>
        <select
          className={selectClass}
          value={d.presetId ?? ""}
          aria-label={tx("切换功能")}
          onChange={(event) => {
            const next = (menu ?? []).find((row) => row.id === event.target.value);
            if (next) apply(resolveSpec(next, specs ?? []), next);
          }}
        >
          {(menu ?? []).map((row) => (
            <option key={row.id} value={row.id}>{row.title}</option>
          ))}
        </select>
      </div>
      <Field label={tx("服务商")}>
        <select
          className={selectClass}
          value={d.providerId ?? providerIds[0] ?? ""}
          onChange={(event) => {
            const providerId = Number(event.target.value);
            apply(pool.find((row) => providerForSpec(row, providers ?? [])?.id === providerId));
          }}
        >
          {providerIds.map((id) => (
            <option key={id} value={id}>{providers?.find((row) => row.id === id)?.name}</option>
          ))}
        </select>
      </Field>
      <Field label={tx("模型 / 工作流")}>
        <select
          className={selectClass}
          value={`${d.targetType ?? ""}:${d.targetId ?? ""}`}
          onChange={(event) => apply(pool.find((row) => `${row.target_type}:${row.target_id}` === event.target.value))}
        >
          {pool
            .filter((row) => providerForSpec(row, providers ?? [])?.id === (d.providerId ?? providerIds[0]))
            .map((row) => (
              <option key={`${row.target_type}:${row.target_id}`} value={`${row.target_type}:${row.target_id}`}>
                {row.display_name}
              </option>
            ))}
        </select>
      </Field>
    </div>
  );
}

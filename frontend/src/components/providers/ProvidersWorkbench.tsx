/** 服务提供方：左侧按启用状态列出，每种类型只打开一份配置。
 * 由 pages/SettingsPage.tsx 导出。调用 /api/v1/providers 与 /catalog。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AudioLines,
  ChevronDown,
  Clapperboard,
  Eye,
  Film,
  GalleryHorizontal,
  GalleryHorizontalEnd,
  Image as ImageIcon,
  ImagePlus,
  Images,
  MessageSquare,
  Mic,
  Pencil,
  RefreshCw,
  Settings,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { api, type ModelItem, type ProviderOut, type ProviderTypeInfo } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { LightboxShell } from "@/components/ui/lightbox";
import { useTx } from "@/i18n/tx";
import { readCatalog } from "@/lib/modelCatalog";

const TABS = [
  { id: "all", label: "全部模型" },
  { id: "llm", label: "对话" },
  { id: "image", label: "图像" },
  { id: "video", label: "视频" },
  { id: "speech", label: "语音" },
] as const;

const SUBS = [
  ["chat", "对话"],
  ["vision", "视觉"],
  ["t2i", "文生图"],
  ["i2i_single", "单图编辑"],
  ["i2i_multi", "多图编辑"],
  ["t2v", "文生视频"],
  ["i2v_first", "首帧"],
  ["i2v_flf", "首尾帧"],
  ["v2v_ref", "参考视频"],
  ["tts", "文字转语音"],
  ["asr", "语音转文字"],
] as const;

const SUB_ICON: Record<string, LucideIcon> = {
  chat: MessageSquare,
  vision: Eye,
  t2i: ImageIcon,
  i2i_single: ImagePlus,
  i2i_multi: Images,
  t2v: Clapperboard,
  i2v_first: GalleryHorizontalEnd,
  i2v_flf: GalleryHorizontal,
  v2v_ref: Film,
  tts: AudioLines,
  asr: Mic,
};

function knownSubs(subs: string[]): string[] {
  return subs.filter((sub) => SUB_ICON[sub]);
}

type ModelKind = "llm" | "image" | "video" | "speech" | "unknown";
type ParamField = NonNullable<ProviderTypeInfo["param_schemas"]>[string][number];

/** 页签、能力和参数都读后端下发的服务商配置，不再在前端另写一份。 */
function kindsOf(info?: ProviderTypeInfo | null): ModelKind[] {
  const allowed = new Set<ModelKind>(["llm", "image", "video", "speech"]);
  return (info?.model_kinds ?? []).filter((id): id is ModelKind => allowed.has(id as ModelKind));
}

function subsForKind(info: ProviderTypeInfo | null | undefined, kind: ModelKind): string[] {
  if (kind === "unknown") return [];
  return info?.sub_capabilities_by_kind?.[kind] ?? [];
}

function offeredSubs(info?: ProviderTypeInfo | null): string[] {
  return kindsOf(info).flatMap((kind) => subsForKind(info, kind));
}

function fieldsFor(info: ProviderTypeInfo | null | undefined, kind: ModelKind, subs: string[]): ParamField[] {
  return (info?.param_schemas?.[kind] ?? []).filter((field) => !field.when_sub || subs.includes(field.when_sub));
}

function subLabel(id: string): string {
  return SUBS.find(([sub]) => sub === id)?.[1] ?? id;
}

function modelInTab(item: ModelItem, tabId: string): boolean {
  if (tabId === "all") return true;
  if (tabId === "speech") return item.category === "tts" || item.category === "asr";
  return item.category === tabId;
}

export function ProvidersWorkbench() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: caps } = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const [query, setQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [folded, setFolded] = useState<{ on: boolean; off: boolean }>({ on: false, off: false });
  const [pending, setPending] = useState<ProviderOut | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [checkModel, setCheckModel] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [draftId, setDraftId] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [draftCategory, setDraftCategory] = useState("llm");
  const [draftSubs, setDraftSubs] = useState<string[]>(["chat"]);

  const needle = query.trim().toLowerCase();
  const types = (caps?.provider_types ?? []).filter((info) =>
    `${info.label} ${info.type} ${info.description}`.toLowerCase().includes(needle),
  );
  const rowOf = (type: string) => {
    const rows = (providers ?? []).filter((item) => item.type === type);
    return rows.find((item) => item.enabled) ?? rows[0] ?? null;
  };
  const activeInfo = (caps?.provider_types ?? []).find((info) => info.type === selectedType) ?? null;
  const listed = selectedType ? rowOf(selectedType) : null;
  const selected = listed ?? (pending?.type === selectedType ? pending : null);
  const catalog = useMemo(() => readCatalog(selected?.extra), [selected]);
  useEffect(() => {
    const kinds = kindsOf(activeInfo);
    if (tab !== "all" && !kinds.includes(tab as ModelKind)) setTab("all");
  }, [activeInfo, tab]);
  const shown = catalog.filter((item) => {
    if (tab === "all") return true;
    if (tab === "speech") return item.category === "tts" || item.category === "asr";
    return item.category === tab;
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["providers"] });
  const saveCatalog = useMutation({
    mutationFn: (models: ModelItem[]) => api.saveProviderCatalog(selected!.id, models),
    onSuccess: () => {
      setMessage(tx("模型目录已保存"));
      void invalidate();
    },
    onError: (err: Error) => setMessage(err.message),
  });
  const create = useMutation({
    mutationFn: (info: ProviderTypeInfo) => {
      if ((providers ?? []).some((item) => item.type === info.type)) {
        return Promise.reject(new Error(tx("这个服务商已经有一份配置")));
      }
      return api.createProvider({
        name: info.label,
        type: info.type,
        base_url: info.default_base_url ?? "",
        api_key: apiKey || undefined,
      });
    },
    onSuccess: (created) => {
      setSelectedType(created.type);
      setPending(created);
      setBaseUrl(created.base_url);
      setApiKey("");
      void invalidate();
    },
    onError: (err: Error) => setMessage(err.message),
  });
  const openType = (info: ProviderTypeInfo) => {
    const row = rowOf(info.type);
    setSelectedType(info.type);
    setMessage(null);
    if (row) setBaseUrl(row.base_url);
  };
  const toggleType = (info: ProviderTypeInfo) => {
    const row = rowOf(info.type);
    if (!row) {
      create.mutate(info);
      return;
    }
    void api.updateProvider(row.id, { enabled: !row.enabled }).then(() => invalidate());
  };

  return (
    <div className="flex max-w-6xl flex-col gap-6">
      <PageHeader
        kind="settings"
        icon={Settings}
        title={tx("服务提供方")}
        description={tx("每种服务商只保留一份配置。打开开关后填写地址和密钥，再启用要用的模型。")}
      />
      <div className="grid min-h-[36rem] overflow-hidden rounded-xl border border-border bg-card grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="border-r border-border p-3">
          <Input
            type="search"
            name="provider-search"
            autoComplete="off"
            value={query}
            placeholder={tx("搜索服务商")}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            className={`mt-3 flex w-full items-center rounded-lg px-2 py-1.5 text-left text-sm ${selectedType == null ? "bg-muted" : "hover:bg-muted/60"}`}
            onClick={() => setSelectedType(null)}
          >
            {tx("全部")}
          </button>
          {(["on", "off"] as const).map((bucket) => {
            const rows = types.filter((info) => {
              const enabled = Boolean(rowOf(info.type)?.enabled);
              return bucket === "on" ? enabled : !enabled;
            });
            if (rows.length === 0) return null;
            const closed = folded[bucket];
            return (
              <section key={bucket} className="mt-3">
                <button
                  type="button"
                  className="mb-1 flex w-full items-center gap-1 px-2 text-xs text-muted-foreground"
                  aria-expanded={!closed}
                  onClick={() => setFolded((current) => ({ ...current, [bucket]: !current[bucket] }))}
                >
                  <ChevronDown className={`size-3.5 transition-transform ${closed ? "-rotate-90" : ""}`} />
                  {bucket === "on" ? tx("已启用") : tx("未启用")}
                  <span className="ml-1">{rows.length}</span>
                </button>
                {!closed && rows.map((info) => {
                  const row = rowOf(info.type);
                  return (
                    <div key={info.type} className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${selectedType === info.type ? "bg-muted" : "hover:bg-muted/60"}`}>
                      <button type="button" className="min-w-0 flex-1 truncate text-left text-sm" onClick={() => openType(info)}>
                        <span className={`mr-2 inline-block size-1.5 rounded-full ${row?.enabled ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
                        {info.label}
                      </button>
                      <Switch
                        label={tx("启用 {name}", { name: info.label })}
                        checked={Boolean(row?.enabled)}
                        onChange={() => toggleType(info)}
                      />
                    </div>
                  );
                })}
              </section>
            );
          })}
        </aside>
        <section className="p-5">
          {!activeInfo ? (
            needle && types.length === 0 ? (
              <p className="text-sm text-muted-foreground">{tx("没有匹配的服务商")}</p>
            ) : (
              <ProviderGallery types={types} rowOf={rowOf} onOpen={openType} onToggle={toggleType} />
            )
          ) : !selected ? (
            <div className="flex max-w-lg flex-col gap-3">
              <h2 className="text-lg font-medium">{activeInfo.label}</h2>
              <p className="text-sm text-muted-foreground">{activeInfo.description}</p>
              {activeInfo.type === "liber_depth" && (
                <p className="text-sm text-muted-foreground">
                  {tx("启用后会列出六种 MiDaS 权重。默认只打开 SwinV2 Large 384。一次转换只用其中一个。")}
                </p>
              )}
              <Button className="w-fit" onClick={() => create.mutate(activeInfo)} disabled={create.isPending}>
                {tx("启用这份配置")}
              </Button>
            </div>
          ) : (
            <>
              <div className="mb-2 flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-medium">{activeInfo.label}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{activeInfo.description}</p>
                </div>
                <Switch
                  label={tx("启用 {name}", { name: activeInfo.label })}
                  checked={selected.enabled}
                  onChange={() => {
                    void api.updateProvider(selected.id, { enabled: !selected.enabled }).then(() => invalidate());
                  }}
                />
              </div>
            <Detail
              provider={selected}
              profile={activeInfo}
              baseUrl={baseUrl || selected.base_url}
              apiKey={apiKey}
              checkModel={checkModel}
              tab={tab}
              shown={shown}
              catalog={catalog}
              message={message}
              draftId={draftId}
              draftLabel={draftLabel}
              draftCategory={draftCategory}
              draftSubs={draftSubs}
              onBaseUrl={setBaseUrl}
              onApiKey={setApiKey}
              onCheckModel={setCheckModel}
              onTab={setTab}
              onDraftId={setDraftId}
              onDraftLabel={setDraftLabel}
              onDraftCategory={(value) => {
                setDraftCategory(value);
                const allowed = subsForKind(activeInfo, value as ModelKind);
                setDraftSubs((current) => {
                  const next = current.filter((id) => allowed.includes(id));
                  return next.length > 0 ? next : allowed.slice(0, 1);
                });
              }}
              onToggleSub={(sub) =>
                setDraftSubs((current) =>
                  current.includes(sub) ? current.filter((item) => item !== sub) : [...current, sub],
                )
              }
              onPatch={(body) => {
                void api.updateProvider(selected.id, body).then(() => invalidate());
              }}
              onSaveCatalog={(models) => saveCatalog.mutate(models)}
              onRefresh={() => {
                void api
                  .fetchProviderModels(selected.id)
                  .then(() => {
                    setMessage(tx("已刷新模型列表"));
                    void invalidate();
                  })
                  .catch((err: Error) => setMessage(err.message));
              }}
              onDelete={() => {
                void api.deleteProvider(selected.id).then(() => {
                  setPending(null);
                  void invalidate();
                });
              }}
              onTest={() => {
                void api.testProvider(selected.id).then((result) => setMessage(result.message));
              }}
              onAddCustom={() => {
                if (!draftId.trim()) return;
                const kinds = kindsOf(activeInfo);
                const kind = (kinds.includes(draftCategory as ModelKind) ? draftCategory : "unknown") as ModelKind;
                const subs = draftSubs.filter((id) => subsForKind(activeInfo, kind).includes(id));
                saveCatalog.mutate([
                  ...catalog,
                  {
                    id: draftId.trim(),
                    label: draftLabel.trim() || draftId.trim(),
                    category: kinds.length === 0 ? "unknown" : categoryFor(kind, subs),
                    sub_capabilities: subs,
                    enabled: true,
                    custom: true,
                  },
                ]);
                setDraftId("");
                setDraftLabel("");
              }}
            />
              </>
            )}
        </section>
      </div>
    </div>
  );
}

function Detail(props: {
  provider: ProviderOut;
  profile: ProviderTypeInfo | null;
  baseUrl: string;
  apiKey: string;
  checkModel: string;
  tab: string;
  shown: ModelItem[];
  catalog: ModelItem[];
  message: string | null;
  draftId: string;
  draftLabel: string;
  draftCategory: string;
  draftSubs: string[];
  onBaseUrl: (value: string) => void;
  onApiKey: (value: string) => void;
  onCheckModel: (value: string) => void;
  onTab: (value: (typeof TABS)[number]["id"]) => void;
  onDraftId: (value: string) => void;
  onDraftLabel: (value: string) => void;
  onDraftCategory: (value: string) => void;
  onToggleSub: (sub: string) => void;
  onPatch: (body: { name?: string; base_url?: string; api_key?: string; enabled?: boolean }) => void;
  onSaveCatalog: (models: ModelItem[]) => void;
  onRefresh: () => void;
  onDelete: () => void;
  onTest: () => void;
  onAddCustom: () => void;
}) {
  const tx = useTx();
  const [editing, setEditing] = useState<ModelItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [manual, setManual] = useState(false);
  const [modelQuery, setModelQuery] = useState("");
  const needle = modelQuery.trim().toLowerCase();
  const visible = props.shown.filter((item) => !needle || `${item.label} ${item.id}`.toLowerCase().includes(needle));
  const toggle = (id: string, on: boolean) => {
    props.onSaveCatalog(props.catalog.map((item) => (item.id === id ? { ...item, enabled: on } : item)));
  };
  const kinds = kindsOf(props.profile);
  const modelTabs = TABS.filter((item) => item.id === "all" || kinds.includes(item.id as ModelKind));
  const manualKind = (
    kinds.includes(props.draftCategory as ModelKind) ? props.draftCategory : kinds[0] ?? "llm"
  ) as ModelKind;
  const manualSubs = subsForKind(props.profile, manualKind);
  const saveItem = (next: ModelItem) => {
    const allowed = new Set(offeredSubs(props.profile));
    const subs = knownSubs(next.sub_capabilities).filter((id) => allowed.has(id));
    props.onSaveCatalog(
      props.catalog.map((item) =>
        item.id === next.id
          ? {
              ...item,
              label: next.label,
              sub_capabilities: subs,
              category: next.category,
              custom: true,
              params: next.params,
            }
          : item,
      ),
    );
    setEditing(null);
  };
  return (
    <div className="flex flex-col">
      <div className="mb-2 flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
          <Trash2 className="size-4" />
          {tx("删除这份配置")}
        </Button>
      </div>
      <SettingRow title={tx("API Key")} hint={props.provider.has_api_key ? tx("已保存，留空表示不修改") : tx("填写后失焦即保存")}>
        <Input
          type="password"
          name="api-key"
          autoComplete="new-password"
          value={props.apiKey}
          onChange={(event) => props.onApiKey(event.target.value)}
          onBlur={() => props.apiKey && props.onPatch({ api_key: props.apiKey })}
        />
      </SettingRow>
      <SettingRow title={tx("API 地址")} hint={tx("必须包含 http:// 或 https://")}>
        <Input
          value={props.baseUrl}
          onChange={(event) => props.onBaseUrl(event.target.value)}
          onBlur={() => props.onPatch({ base_url: props.baseUrl })}
        />
      </SettingRow>
      <SettingRow title={tx("连通性检查")} hint={tx("测试密钥与地址是否正确")}>
        <select className={selectClass} value={props.checkModel} onChange={(event) => props.onCheckModel(event.target.value)}>
          <option value="">{tx("服务默认检查")}</option>
          {props.catalog.filter((item) => item.enabled).map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
        <Button variant="outline" size="sm" onClick={props.onTest}>{tx("检查")}</Button>
      </SettingRow>
      {props.message && <p className="py-2 text-sm text-muted-foreground">{props.message}</p>}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{tx("模型列表")}</h3>
        <div className="flex items-center gap-2">
          <Input
            type="search"
            name="model-search"
            autoComplete="off"
            value={modelQuery}
            placeholder={tx("搜索模型")}
            aria-label={tx("搜索模型")}
            className="h-8 w-40"
            onChange={(event) => setModelQuery(event.target.value)}
          />
          <Button variant="outline" size="sm" onClick={props.onRefresh}>
            <RefreshCw className="size-4" />
            {tx("获取模型列表")}
          </Button>
        </div>
      </div>
      <div
        className="mt-3 flex gap-4 border-b border-border text-sm"
        role="tablist"
        aria-label={tx("模型列表")}
        onKeyDown={(event) => {
          if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
          const index = modelTabs.findIndex((item) => item.id === props.tab);
          const delta = event.key === "ArrowRight" ? 1 : -1;
          const next = modelTabs[(index + delta + modelTabs.length) % modelTabs.length];
          props.onTab(next.id);
          document.getElementById(`model-tab-${next.id}`)?.focus();
          event.preventDefault();
        }}
      >
        {modelTabs.map((item) => {
          const selected = props.tab === item.id;
          const count = props.catalog.filter((model) => modelInTab(model, item.id)).length;
          return (
            <button
              key={item.id}
              id={`model-tab-${item.id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls="model-tab-panel"
              tabIndex={selected ? 0 : -1}
              className={`border-b-2 px-1 py-2 ${selected ? "border-primary text-foreground" : "border-transparent text-muted-foreground"}`}
              onClick={() => props.onTab(item.id)}
            >
              {tx(item.label)} {count}
            </button>
          );
        })}
      </div>
      <div id="model-tab-panel" role="tabpanel" aria-labelledby={`model-tab-${props.tab}`}>
      <ModelList
        title={tx("已启用")}
        items={visible.filter((item) => item.enabled)}
        providerType={props.provider.type}
        allowedSubs={offeredSubs(props.profile)}
        onToggle={toggle}
        onEdit={setEditing}
      />
      <ModelList
        title={tx("未启用")}
        items={visible.filter((item) => !item.enabled)}
        providerType={props.provider.type}
        allowedSubs={offeredSubs(props.profile)}
        onToggle={toggle}
        onEdit={setEditing}
      />
      {needle && visible.length === 0 && <p className="py-6 text-sm text-muted-foreground">{tx("没有匹配的模型")}</p>}
      {!needle && visible.length === 0 && (
        <p className="py-6 text-sm text-muted-foreground">
          {props.tab === "all"
            ? tx("还没有模型。可以获取列表，或在下面手动添加。")
            : tx("{name} 可以做{kind}，列表里还没有。未分类的模型在「全部模型」。", {
                name: props.provider.name,
                kind: tx(modelTabs.find((item) => item.id === props.tab)?.label ?? ""),
              })}
        </p>
      )}
      </div>
      {editing && (
        <ModelSettings
          item={editing}
          profile={props.profile}
          onClose={() => setEditing(null)}
          onSave={saveItem}
        />
      )}
      {confirmDelete && (
        <LightboxShell onClose={() => setConfirmDelete(false)} ariaLabel={tx("删除这份配置")} className="max-w-md">
          <div className="flex flex-col gap-4 px-5 py-4">
            <h2 className="text-base font-medium">{tx("删除这份配置")}</h2>
            <p className="text-sm text-muted-foreground">
              {tx("删除后，这份配置的地址、密钥和模型列表都会去掉。已生成的作品还在。")}
            </p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>{tx("取消")}</Button>
              <Button type="button" variant="outline" className="text-danger" onClick={props.onDelete}>
                {tx("删除这份配置")}
              </Button>
            </div>
          </div>
        </LightboxShell>
      )}
      <div className="mt-4 rounded-lg border border-dashed border-border p-3">
        <button
          type="button"
          className="text-sm font-medium"
          aria-expanded={manual}
          onClick={() => setManual((open) => !open)}
        >
          {tx("手动添加模型")}
        </button>
        {manual && (
          <div className="mt-2">
            <p className="mb-2 text-xs text-muted-foreground">
              {kinds.length === 0
                ? tx("这个服务商的模型不在这里选功能。画布用的是工作流包。")
                : tx("勾选后，它会出现在对应的画布功能里。不勾选时只出现在「全部模型」。")}
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              <Input
                aria-label={tx("模型 ID")}
                placeholder={tx("例如 qwen-plus")}
                value={props.draftId}
                onChange={(event) => props.onDraftId(event.target.value)}
              />
              <Input placeholder={tx("简称")} aria-label={tx("简称")} value={props.draftLabel} onChange={(event) => props.onDraftLabel(event.target.value)} />
              {kinds.length > 1 && (
                <select className={selectClass} aria-label={tx("类型")} value={props.draftCategory} onChange={(event) => props.onDraftCategory(event.target.value)}>
                  {kinds.map((kind) => (
                    <option key={kind} value={kind}>{tx(KIND_OPTIONS.find((item) => item.id === kind)?.label ?? kind)}</option>
                  ))}
                </select>
              )}
            </div>
            {manualSubs.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {manualSubs.map((id) => (
                  <label key={id} className="flex items-center gap-1">
                    <input type="checkbox" checked={props.draftSubs.includes(id)} onChange={() => props.onToggleSub(id)} />
                    {tx(subLabel(id))}
                  </label>
                ))}
              </div>
            )}
            <Button className="mt-2" size="sm" onClick={props.onAddCustom}>{tx("添加")}</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function Switch({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={checked}
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? "bg-primary" : "bg-muted"}`}
      onClick={onChange}
    >
      <span className={`absolute top-0.5 size-4 rounded-full bg-white transition-transform ${checked ? "left-4" : "left-0.5"}`} />
    </button>
  );
}

const MARKS: Record<string, string> = {
  openai_compatible: "/provider-icons/openai.png",
  openai_tts: "/provider-icons/openai.png",
  openai_stt: "/provider-icons/openai.png",
  openai_images: "/provider-icons/openai.png",
  openai: "/provider-icons/openai.png",
  chatgpt: "/provider-icons/openai.png",
  anthropic: "/provider-icons/anthropic.png",
  google: "/provider-icons/google.png",
  deepseek: "/provider-icons/deepseek.png",
  kimi_code: "/provider-icons/kimi.png",
  aliyun_bailian: "/provider-icons/bailian.png",
  ollama: "/provider-icons/ollama.png",
  volcengine_ark: "/provider-icons/volcengine.png",
  volcengine_speech: "/provider-icons/doubao.png",
  comfyui: "/provider-icons/comfyui.png",
  edge_tts: "/provider-icons/microsoft.png",
  liber_speech: "/provider-icons/liber.svg",
  liber_depth: "/provider-icons/liber.svg",
};

function ProviderMark({ type, size = "md" }: { type: string; size?: "md" | "sm" }) {
  const box = size === "sm" ? "size-8 rounded-lg" : "size-11 rounded-2xl";
  const glyph = size === "sm" ? "size-5" : "size-8";
  const src = MARKS[type];
  if (!src) {
    return <span className={`grid ${box} place-items-center bg-muted text-xs font-medium`}>{type.slice(0, 2).toUpperCase()}</span>;
  }
  const onLight =
    type === "ollama"
      ? "/provider-icons/ollama-light.png"
      : type === "anthropic"
        ? "/provider-icons/anthropic-light.png"
        : type === "kimi_code"
          ? "/provider-icons/kimi-light.png"
          : src.endsWith("openai.png")
            ? "/provider-icons/openai-light.png"
            : null;
  if (onLight) {
    return (
      <span className={`grid ${box} place-items-center bg-muted`}>
        <img src={onLight} alt="" className={`${glyph} object-contain dark:hidden`} />
        <img src={src} alt="" className={`hidden ${glyph} object-contain dark:block`} />
      </span>
    );
  }
  return <img src={src} alt="" className={`${box} bg-muted object-contain p-1`} />;
}

function ProviderGallery({
  types,
  rowOf,
  onOpen,
  onToggle,
}: {
  types: ProviderTypeInfo[];
  rowOf: (type: string) => ProviderOut | null;
  onOpen: (info: ProviderTypeInfo) => void;
  onToggle: (info: ProviderTypeInfo) => void;
}) {
  const tx = useTx();
  const enabled = types.filter((info) => rowOf(info.type)?.enabled);
  const disabled = types.filter((info) => !rowOf(info.type)?.enabled);
  const render = (info: ProviderTypeInfo) => {
    const row = rowOf(info.type);
    return (
      <article key={info.type} className="flex min-h-36 flex-col justify-between rounded-2xl border border-border bg-background p-4">
        <div className="flex items-start justify-between gap-3">
          <button type="button" className="text-left" onClick={() => onOpen(info)} aria-label={info.label}>
            <ProviderMark type={info.type} />
          </button>
          <Switch label={tx("启用 {name}", { name: info.label })} checked={Boolean(row?.enabled)} onChange={() => onToggle(info)} />
        </div>
        <button type="button" className="mt-3 text-left" onClick={() => onOpen(info)}>
          <h2 className="text-sm font-medium">{info.label}</h2>
          <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{info.description}</p>
        </button>
      </article>
    );
  };
  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-3 text-sm font-medium">{tx("已启用服务商")}<span className="ml-2 text-xs text-muted-foreground">{enabled.length}</span></h2>
        {enabled.length === 0 ? (
          <p className="text-sm text-muted-foreground">{tx("还没有启用的服务商")}</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{enabled.map(render)}</div>
        )}
      </section>
      <section>
        <h2 className="mb-3 text-sm font-medium">{tx("未启用服务商")}<span className="ml-2 text-xs text-muted-foreground">{disabled.length}</span></h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{disabled.map(render)}</div>
      </section>
    </div>
  );
}

function SettingRow({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-b border-border py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="sm:max-w-xs">
        <p className="text-sm font-medium">{title}</p>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="flex w-full items-center gap-2 sm:max-w-md sm:justify-end">{children}</div>
    </div>
  );
}

function categoryOf(subs: string[]): string {
  if (subs.some((item) => ["t2v", "t2v_enhance", "i2v_first", "i2v_flf", "i2v_orbit", "i2v_enhance", "v2v_ref", "avatar", "motion", "video_analysis"].includes(item))) {
    return "video";
  }
  if (subs.some((item) => ["t2i", "i2i_single", "i2i_multi", "inpaint", "color_grade", "outfit_swap", "depth_pose", "depth_gen", "upscale", "analysis"].includes(item))) {
    return "image";
  }
  if (subs.includes("tts")) return "tts";
  if (subs.includes("asr")) return "asr";
  return subs.length > 0 ? "llm" : "unknown";
}

function ModelList({
  title,
  items,
  providerType,
  allowedSubs,
  onToggle,
  onEdit,
}: {
  title: string;
  items: ModelItem[];
  providerType: string;
  allowedSubs: string[];
  onToggle: (id: string, enabled: boolean) => void;
  onEdit: (item: ModelItem) => void;
}) {
  const tx = useTx();
  if (items.length === 0) return null;
  return (
    <div className="mt-4">
      <p className="mb-1 text-xs text-muted-foreground">{title}</p>
      <ul>
        {items.map((item) => {
          const marks = knownSubs(item.sub_capabilities).filter((id) => allowedSubs.includes(id));
          return (
            <li key={item.id} className="flex items-center gap-3 border-b border-border py-2.5">
              <ProviderMark type={providerType} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 items-center gap-1">
                  <p className="truncate text-sm font-medium">{item.label}</p>
                  <button
                    type="button"
                    className="grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label={tx("编辑 {name}", { name: item.label })}
                    onClick={() => onEdit(item)}
                  >
                    <Pencil className="size-3.5" />
                  </button>
                </div>
                {item.label !== item.id && (
                  <p className="truncate font-mono text-xs text-muted-foreground">{item.id}</p>
                )}
              </div>
              <span className="flex max-w-[40%] shrink-0 flex-wrap justify-end gap-x-2 text-xs text-muted-foreground">
                {marks.length === 0 ? (
                  <span>{tx("未分类")}</span>
                ) : (
                  marks.map((sub) => <span key={sub}>{tx(subLabel(sub))}</span>)
                )}
              </span>
              <Switch
                label={tx(item.enabled ? "停用 {name}" : "启用 {name}", { name: item.label })}
                checked={item.enabled}
                onChange={() => onToggle(item.id, !item.enabled)}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const KIND_OPTIONS: { id: ModelKind; label: string }[] = [
  { id: "llm", label: "对话" },
  { id: "image", label: "图像" },
  { id: "video", label: "视频" },
  { id: "speech", label: "语音" },
  { id: "unknown", label: "未知" },
];

function kindOf(item: ModelItem): ModelKind {
  if (item.category === "tts" || item.category === "asr") return "speech";
  if (item.category === "image" || item.category === "video" || item.category === "llm") return item.category;
  return "unknown";
}

function categoryFor(kind: ModelKind, subs: string[]): string {
  if (kind === "unknown") return "unknown";
  const derived = categoryOf(subs);
  if (derived !== "unknown") return derived;
  return kind === "speech" ? "tts" : kind;
}

function savedDefaults(item: ModelItem): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(item.params?.defaults ?? {})) {
    next[key] = String(value);
  }
  return next;
}

function ModelSettings({
  item,
  profile,
  onClose,
  onSave,
}: {
  item: ModelItem;
  profile: ProviderTypeInfo | null;
  onClose: () => void;
  onSave: (item: ModelItem) => void;
}) {
  const tx = useTx();
  const kinds = kindsOf(profile);
  const baseline = knownSubs(item.sub_capabilities);
  const initialKind = kinds.includes(kindOf(item)) ? kindOf(item) : "unknown";
  const [label, setLabel] = useState(item.label);
  const [kind, setKind] = useState<ModelKind>(initialKind);
  const [subs, setSubs] = useState<string[]>(() =>
    subsForKind(profile, initialKind).filter((id) => baseline.includes(id)),
  );
  const [maxOutput, setMaxOutput] = useState(item.params?.max_output ? String(item.params.max_output) : "");
  const [defaults, setDefaults] = useState<Record<string, string>>(savedDefaults(item));
  const allowed = subsForKind(profile, kind);
  const schemaFields = fieldsFor(profile, kind, subs);
  const tokenField = schemaFields.find((field) => field.key === "max_output");
  const defaultFields = schemaFields.filter((field) => field.key !== "max_output");
  const offered = offeredSubs(profile);
  const dropped = baseline.filter((id) => offered.includes(id) && (kind === "unknown" || !allowed.includes(id)));
  const chooseKind = (next: ModelKind) => {
    setKind(next);
    if (next === "unknown") {
      setSubs([]);
      return;
    }
    const ids = new Set(subsForKind(profile, next));
    setSubs(baseline.filter((id) => ids.has(id)));
  };
  const toggleSub = (id: string) => {
    setSubs((current) => (current.includes(id) ? current.filter((sub) => sub !== id) : [...current, id]));
  };
  return (
    <LightboxShell onClose={onClose} ariaLabel={tx("模型设置")} className="max-w-lg">
      <form
        className="flex max-h-[90vh] flex-col"
        onSubmit={(event) => {
          event.preventDefault();
          const nextSubs = kind === "unknown" ? [] : subs.filter((id) => allowed.includes(id));
          const params: NonNullable<ModelItem["params"]> = {};
          const tokens = Number(maxOutput);
          if (tokenField && maxOutput.trim() && Number.isFinite(tokens)) {
            const low = tokenField.min ?? 1;
            const high = tokenField.max ?? 200000;
            if (tokens >= low) params.max_output = Math.min(high, Math.max(low, Math.round(tokens)));
          }
          const saved: Record<string, string | number | boolean> = {};
          for (const field of defaultFields) {
            const raw = defaults[field.key] ?? "";
            if (raw === "") continue;
            if (field.type === "bool") {
              if (raw !== "true" && raw !== "false") continue;
              saved[field.key] = raw === "true";
            } else if (field.type === "int") {
              const number = Number(raw);
              if (!Number.isFinite(number)) continue;
              const low = field.min ?? number;
              const high = field.max ?? number;
              saved[field.key] = Math.min(high, Math.max(low, Math.round(number)));
            } else {
              saved[field.key] = raw;
            }
          }
          if (Object.keys(saved).length > 0) params.defaults = saved;
          onSave({
            ...item,
            label: label.trim() || item.id,
            sub_capabilities: nextSubs,
            category: categoryFor(kind, nextSubs),
            custom: true,
            params: params.max_output || params.defaults ? params : undefined,
          });
        }}
      >
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-base font-medium">{tx("模型设置")}</h2>
        </div>
        <div className="flex flex-col gap-4 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{tx("模型 ID")}</span>
            <p className="font-mono text-sm text-muted-foreground">{item.id}</p>
            <span className="text-xs text-muted-foreground">{tx("调用时使用这个 ID，这里不能改。")}</span>
          </div>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{tx("展示名称")}</span>
            <Input value={label} onChange={(event) => setLabel(event.target.value)} />
          </label>
          {kinds.length > 0 ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm font-medium">{tx("类型")}</legend>
              <div className="flex flex-wrap gap-2">
                {KIND_OPTIONS.filter((option) => kinds.includes(option.id)).map((option) => (
                  <label key={option.id} className="flex items-center gap-1.5 rounded-lg px-1 py-1 text-sm">
                    <input
                      type="radio"
                      name="model-kind"
                      checked={kind === option.id}
                      onChange={() => chooseKind(option.id)}
                    />
                    {tx(option.label)}
                  </label>
                ))}
              </div>
              {kind !== "unknown" && (
                <button type="button" className="self-start text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={() => chooseKind("unknown")}>
                  {tx("标为未分类")}
                </button>
              )}
              {dropped.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {tx("将取消：{names}", { names: dropped.map((id) => tx(subLabel(id))).join("、") })}
                </p>
              )}
            </fieldset>
          ) : (
            <p className="text-xs text-muted-foreground">{tx("这个服务商的模型不在这里选功能。画布用的是工作流包。")}</p>
          )}
          {kind === "unknown" && kinds.length > 0 && (
            <p className="text-xs text-muted-foreground">{tx("未知模型不进入画布功能。确认用途后再选择类型。")}</p>
          )}
          {kind !== "unknown" && allowed.length > 0 && (
            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm font-medium">{tx("能力")}</legend>
              <p className="text-xs text-muted-foreground">{tx("勾选后进入对应的画布功能。不认识的类型不会显示。")}</p>
              {allowed.map((id) => {
                const text = SUBS.find(([sub]) => sub === id)?.[1] ?? id;
                const Icon = SUB_ICON[id];
                return (
                  <label key={id} className="flex items-center gap-2 rounded-lg px-1 py-1 text-sm hover:bg-muted/60">
                    <input type="checkbox" checked={subs.includes(id)} onChange={() => toggleSub(id)} />
                    {Icon && <Icon className="size-3.5 text-muted-foreground" aria-hidden />}
                    {tx(text)}
                  </label>
                );
              })}
            </fieldset>
          )}
          {tokenField && (
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">{tx(tokenField.label)}</span>
              <Input
                type="number"
                min={tokenField.min ?? 1}
                max={tokenField.max ?? 200000}
                value={maxOutput}
                onChange={(event) => setMaxOutput(event.target.value)}
              />
              <span className="text-xs text-muted-foreground">
                {tx("留空则用服务默认。对话请求会带上这个上限。")}
              </span>
            </label>
          )}
          {defaultFields.length > 0 && (
            <fieldset className="flex flex-col gap-3">
              <legend className="text-sm font-medium">{tx("模型默认参数")}</legend>
              <p className="text-xs text-muted-foreground">
                {tx("这些值会成为画布上该模型的初始参数，节点里仍可修改。")}
              </p>
              {defaultFields.map((field) => (
                <label key={field.key} className="flex flex-col gap-1.5 text-sm">
                  <span>{tx(field.label)}</span>
                  {field.type === "int" ? (
                    <Input
                      type="number"
                      min={field.min ?? undefined}
                      max={field.max ?? undefined}
                      value={defaults[field.key] ?? ""}
                      placeholder={tx("留空使用默认")}
                      onChange={(event) =>
                        setDefaults((current) => ({ ...current, [field.key]: event.target.value }))
                      }
                    />
                  ) : field.options && field.options.length > 0 ? (
                    <select
                      className={selectClass}
                      value={defaults[field.key] ?? ""}
                      onChange={(event) =>
                        setDefaults((current) => ({ ...current, [field.key]: event.target.value }))
                      }
                    >
                      <option value="">{tx("留空使用默认")}</option>
                      {field.options.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  ) : field.type === "bool" ? (
                    <select
                      className={selectClass}
                      value={defaults[field.key] ?? ""}
                      onChange={(event) =>
                        setDefaults((current) => ({ ...current, [field.key]: event.target.value }))
                      }
                    >
                      <option value="">{tx("留空使用默认")}</option>
                      <option value="true">{tx("开启")}</option>
                      <option value="false">{tx("关闭")}</option>
                    </select>
                  ) : (
                    <Input
                      value={defaults[field.key] ?? ""}
                      placeholder={tx("留空使用默认")}
                      onChange={(event) =>
                        setDefaults((current) => ({ ...current, [field.key]: event.target.value }))
                      }
                    />
                  )}
                </label>
              ))}
            </fieldset>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose}>{tx("取消")}</Button>
          <Button type="submit">{tx("保存")}</Button>
        </div>
      </form>
    </LightboxShell>
  );
}

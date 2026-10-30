/** 资源 → 插件：卡片只放图标、名称和说明。点开后才看路径、模型和启停。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, AudioLines, Layers, type LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api, type PluginOut } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";

const ICONS: Record<string, LucideIcon> = {
  speech: AudioLines,
  depth: Layers,
};

const DEPTH_MODELS: { id: string; role: string }[] = [
  { id: "dpt_swin2_large_384", role: "默认。SwinV2 Large，边长 384。安装时只下载这一份。" },
  { id: "dpt_beit_large_512", role: "BEiT Large，边长 512。边缘更细，更慢。" },
  { id: "dpt_swin2_tiny_256", role: "SwinV2 Tiny，边长 256。更快，细节少。" },
  { id: "dpt_large_384", role: "上一代 DPT Large，边长 384。" },
  { id: "dpt_hybrid_384", role: "DPT Hybrid，边长 384，体积更小。" },
  { id: "midas_v21_small_256", role: "MiDaS v2.1 Small，边长 256，最轻。" },
];

const PHASE_LABEL: Record<string, string> = {
  venv: "正在准备 Python 环境",
  torch: "正在安装 PyTorch",
  packages: "正在安装插件依赖",
  model: "正在下载深度模型",
};

function isInstalling(plugin: PluginOut): boolean {
  return Boolean(plugin.install_phase);
}

function statusKey(plugin: PluginOut): "运行中" | "安装中" | "已安装" | "未安装" {
  if (plugin.running) return "运行中";
  if (isInstalling(plugin)) return "安装中";
  if (plugin.installed) return "已安装";
  return "未安装";
}

export function PluginsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const plugins = useQuery({
    queryKey: ["plugins"],
    queryFn: api.listPlugins,
    refetchInterval: (item) =>
      item.state.data?.some(
        (plugin) =>
          Boolean(plugin.install_phase) ||
          plugin.model_status === "downloading" ||
          plugin.env_status === "installing",
      )
        ? 2000
        : false,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["plugins"] });
    void queryClient.invalidateQueries({ queryKey: ["providers"] });
  };
  const install = useMutation({
    mutationFn: (id: string) => api.installPlugin(id),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err: Error) => setError(err.message),
  });
  const uninstall = useMutation({
    mutationFn: (id: string) => api.uninstallPlugin(id),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err: Error) => setError(err.message),
  });
  const toggle = useMutation({
    mutationFn: (plugin: PluginOut) =>
      plugin.enabled ? api.disablePlugin(plugin.id) : api.enablePlugin(plugin.id),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err: Error) => setError(err.message),
  });

  const needle = query.trim().toLowerCase();
  const visible = useMemo(
    () =>
      (plugins.data ?? []).filter((plugin) =>
        `${plugin.name} ${plugin.description}`.toLowerCase().includes(needle),
      ),
    [plugins.data, needle],
  );
  const selected = (plugins.data ?? []).find((plugin) => plugin.id === selectedId) ?? null;
  const busy = install.isPending || uninstall.isPending || toggle.isPending;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kind="image"
        icon={Layers}
        title={tx("插件")}
        description={tx("搜索后点开卡片，再安装或启动本机进程。")}
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="sr-only" htmlFor="plugin-search">
          {tx("搜索插件")}
        </label>
        <Input
          id="plugin-search"
          value={query}
          placeholder={tx("搜索插件")}
          onChange={(event) => setQuery(event.target.value)}
          className="sm:max-w-xs"
        />
        <p className="text-sm text-muted-foreground">
          {tx("连接远程主机请到")}{" "}
          <Link className="text-primary underline-offset-2 hover:underline" to="/settings">
            {tx("服务提供方")}
          </Link>{" "}
          {tx("配置地址。")}
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {selected ? (
        <PluginDetail
          plugin={selected}
          busy={busy}
          onBack={() => setSelectedId(null)}
          onInstall={() => install.mutate(selected.id)}
          onUninstall={() => uninstall.mutate(selected.id)}
          onToggle={() => toggle.mutate(selected)}
        />
      ) : visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">{tx("没有匹配的插件")}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((plugin) => {
            const Icon = ICONS[plugin.id] ?? Layers;
            const status = statusKey(plugin);
            return (
              <button
                key={plugin.id}
                type="button"
                onClick={() => setSelectedId(plugin.id)}
                className="flex min-h-36 flex-col rounded-2xl border border-border bg-card p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="grid size-10 place-items-center rounded-xl border border-border bg-muted text-foreground">
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="mt-4 flex items-center gap-2">
                  <span className="text-sm font-medium text-balance">{plugin.name}</span>
                  <span className={statusClass(status)}>{tx(status)}</span>
                </span>
                <span className="mt-1 line-clamp-3 text-sm text-pretty text-muted-foreground">
                  {plugin.description}
                </span>
                <InstallBar plugin={plugin} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PluginDetail({
  plugin,
  busy,
  onBack,
  onInstall,
  onUninstall,
  onToggle,
}: {
  plugin: PluginOut;
  busy: boolean;
  onBack: () => void;
  onInstall: () => void;
  onUninstall: () => void;
  onToggle: () => void;
}) {
  const tx = useTx();
  const Icon = ICONS[plugin.id] ?? Layers;
  const launch = plugin.launch === "docker" ? "Docker" : "Python";
  return (
    <section className="flex max-w-3xl flex-col gap-5">
      <button
        type="button"
        onClick={onBack}
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="size-4" aria-hidden />
        {tx("返回全部插件")}
      </button>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-border bg-muted">
            <Icon className="size-5" aria-hidden />
          </span>
          <div>
            <h2 className="text-lg font-medium text-balance">{plugin.name}</h2>
            <p className="mt-1 text-sm text-pretty text-muted-foreground">{plugin.description}</p>
          </div>
        </div>
        {isInstalling(plugin) ? (
          <span className="mt-1 animate-pulse rounded-full border border-info/40 px-2 py-0.5 text-xs text-info">
            {tx("安装中")}
          </span>
        ) : (
          <button
            type="button"
            role="switch"
            aria-checked={plugin.enabled}
            aria-label={plugin.enabled ? tx("禁用") : tx("启用")}
            disabled={!plugin.installed || busy}
            onClick={onToggle}
            className={`relative mt-1 h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-40 ${
              plugin.enabled ? "bg-primary" : "bg-muted"
            }`}
          >
            <span
              className={`absolute top-0.5 size-4 rounded-full bg-white transition-transform ${
                plugin.enabled ? "left-4" : "left-0.5"
              }`}
            />
          </button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={plugin.installed ? onUninstall : onInstall}
        >
          {plugin.installed ? tx("卸载") : tx("安装")}
        </Button>
        <span className={statusClass(statusKey(plugin))}>{tx(statusKey(plugin))}</span>
      </div>
      <InstallBar plugin={plugin} />
      <dl className="grid gap-3 text-sm">
        <DetailRow label={tx("程序目录")} value={plugin.code_dir || tx("未找到插件程序")} />
        <DetailRow label={tx("模型目录")} value={plugin.models_dir} />
        {plugin.launch !== "docker" && <DetailRow label={tx("环境目录")} value={plugin.env_dir} />}
        <DetailRow label={tx("启动方式")} value={launch} />
        <DetailRow label={tx("端口")} value={String(plugin.port)} />
      </dl>
      {plugin.id === "speech" && plugin.model_status === "empty" && !plugin.install_phase && (
        <p className="text-sm text-muted-foreground">{tx("语音模型会在第一次合成时下载到这个目录")}</p>
      )}
      {plugin.id === "depth" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            {tx("一次转换只用一个模型。目录里没有对应权重时，这一项不会参与推理。")}
          </p>
          <ul className="flex flex-col gap-2">
            {DEPTH_MODELS.map((item) => (
              <li key={item.id} className="text-sm">
                <span className="font-medium">{item.id}</span>
                <span className="text-muted-foreground"> · {tx(item.role)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {plugin.last_error && <p className="text-sm text-destructive">{plugin.last_error}</p>}
    </section>
  );
}

function statusClass(status: "运行中" | "安装中" | "已安装" | "未安装"): string {
  if (status === "运行中") return "text-xs text-success";
  if (status === "安装中") return "animate-pulse text-xs text-info";
  return "text-xs text-muted-foreground";
}

function InstallBar({ plugin }: { plugin: PluginOut }) {
  const tx = useTx();
  if (!plugin.install_phase) return null;
  const label = PHASE_LABEL[plugin.install_phase] ?? "安装中";
  const value = Math.max(0, Math.min(100, plugin.install_progress || 0));
  const indeterminate = value <= 1;
  return (
    <div className="mt-3 flex flex-col gap-1">
      <div className="flex items-center justify-between gap-3 text-xs text-info">
        <span>{tx(label)}</span>
        {!indeterminate && <span className="tabular-nums">{value}%</span>}
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : value}
        aria-label={tx(label)}
        className="relative h-1.5 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-info"
          style={{ width: indeterminate ? "35%" : `${value}%` }}
        />
        {indeterminate && <div className="progress-shine pointer-events-none absolute inset-0" />}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-border pb-3 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-all">{value}</dd>
    </div>
  );
}

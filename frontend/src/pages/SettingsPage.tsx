import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlugZap, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { api, type ProviderOut, type TestResult } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: caps } = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities });
  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });

  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [rowFeedback, setRowFeedback] = useState<Record<number, TestResult>>({});

  const selectedType = caps?.provider_types.find((t) => t.type === type);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["providers"] });

  const create = useMutation({
    mutationFn: () =>
      api.createProvider({
        name,
        type,
        base_url: baseUrl,
        api_key: apiKey || undefined,
      }),
    onSuccess: () => {
      setName("");
      setType("");
      setBaseUrl("");
      setApiKey("");
      setFormError(null);
      invalidate();
    },
    onError: (err) => setFormError(err.message),
  });

  const test = useMutation({
    mutationFn: (id: number) => api.testProvider(id),
    onSuccess: (result, id) => setRowFeedback((prev) => ({ ...prev, [id]: result })),
    onError: (err, id) =>
      setRowFeedback((prev) => ({ ...prev, [id]: { ok: false, message: err.message } })),
  });

  const fetchModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: (_models, id) => {
      setRowFeedback((prev) => ({ ...prev, [id]: { ok: true, message: "模型列表已更新" } }));
      invalidate();
    },
    onError: (err, id) =>
      setRowFeedback((prev) => ({ ...prev, [id]: { ok: false, message: err.message } })),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteProvider(id),
    onSuccess: invalidate,
  });

  const typeLabel = (p: ProviderOut) =>
    caps?.provider_types.find((t) => t.type === p.type)?.label ?? p.type;

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">服务提供方</h1>

      <Card>
        <CardHeader>
          <CardTitle>添加 Provider</CardTitle>
          <CardDescription>对接局域网或云端的模型服务；密钥加密存储。</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              setFormError(null);
              create.mutate();
            }}
          >
            <select
              className="h-9 rounded-md border border-border bg-transparent px-3 text-sm"
              value={type}
              required
              onChange={(e) => {
                const t = caps?.provider_types.find((x) => x.type === e.target.value);
                setType(e.target.value);
                if (t?.default_base_url && !baseUrl) setBaseUrl(t.default_base_url);
              }}
            >
              <option value="" disabled>
                选择类型…
              </option>
              {caps?.provider_types.map((t) => (
                <option key={t.type} value={t.type}>
                  {t.label}
                </option>
              ))}
            </select>
            <Input placeholder="名称（如：家里 Ollama）" value={name} required onChange={(e) => setName(e.target.value)} />
            <Input
              className="sm:col-span-2"
              placeholder={selectedType?.default_base_url ?? "Base URL（如 http://192.168.1.10:11434）"}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
            <Input
              className="sm:col-span-2"
              type="password"
              placeholder={selectedType?.requires_api_key ? "API Key（必填）" : "API Key（可选）"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required={selectedType?.requires_api_key}
            />
            {selectedType?.description && (
              <p className="text-xs text-muted-foreground sm:col-span-2">{selectedType.description}</p>
            )}
            {formError && <p className="text-sm text-red-500 sm:col-span-2">{formError}</p>}
            <Button type="submit" disabled={create.isPending} className="sm:w-fit">
              {create.isPending ? "添加中…" : "添加"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        {providers?.length === 0 && (
          <p className="text-sm text-muted-foreground">还没有 Provider，先添加一个。</p>
        )}
        {providers?.map((p) => (
          <Card key={p.id}>
            <CardContent className="flex flex-wrap items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{p.name}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{typeLabel(p)}</span>
                  {!p.enabled && <span className="rounded bg-muted px-1.5 py-0.5 text-xs">已停用</span>}
                </div>
                <div className="truncate text-sm text-muted-foreground">{p.base_url}</div>
                <div className="text-xs text-muted-foreground">
                  {p.models.length > 0 ? `${p.models.length} 个模型` : "未拉取模型列表"}
                  {p.has_api_key ? " · 已配置密钥" : ""}
                </div>
                {rowFeedback[p.id] && (
                  <div className={`text-xs ${rowFeedback[p.id].ok ? "text-green-600" : "text-red-500"}`}>
                    {rowFeedback[p.id].message}
                  </div>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => test.mutate(p.id)} disabled={test.isPending}>
                <PlugZap /> 测试
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchModels.mutate(p.id)}
                disabled={fetchModels.isPending}
              >
                <RefreshCw /> 模型
              </Button>
              <Button variant="ghost" size="icon" onClick={() => remove.mutate(p.id)} title="删除">
                <Trash2 />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

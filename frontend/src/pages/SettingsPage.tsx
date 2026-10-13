import { Settings } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlugZap, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { api, type ProviderOut, type TestResult } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: caps } = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities });
  const {
    data: providers,
    isError: providersFailed,
    error: providersError,
  } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });

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
      <PageHeader kind="settings" icon={Settings} title="服务提供方" description="对接局域网或云端模型服务，密钥加密后保存。" />

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
            <Field label="类型" hint={selectedType?.description ?? "先选择服务类型，再填写地址。"}>
              <select
                className={selectClass}
                value={type}
                required
                onChange={(e) => {
                  const next = caps?.provider_types.find((x) => x.type === e.target.value);
                  setType(e.target.value);
                  if (next?.default_base_url && !baseUrl) setBaseUrl(next.default_base_url);
                }}
              >
                <option value="" disabled>
                  选择类型…
                </option>
                {caps?.provider_types.map((item) => (
                  <option key={item.type} value={item.type}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="名称" hint="方便自己区分，例如家里的 Ollama。">
              <Input value={name} required onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field className="sm:col-span-2" label="Base URL" hint="服务根地址。局域网机器请填那台机器的 IP 和端口。">
              <Input
                placeholder={selectedType?.default_base_url ?? "例如 http://192.168.1.10:11434"}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </Field>
            <Field
              className="sm:col-span-2"
              label="API Key"
              hint={selectedType?.requires_api_key ? "这个类型必须填写，保存时会加密。" : "没有密钥可以留空。填写后会加密保存。"}
            >
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required={selectedType?.requires_api_key}
              />
            </Field>
            {formError && <p className="text-sm text-red-500 sm:col-span-2">{formError}</p>}
            <Button type="submit" disabled={create.isPending} className="sm:w-fit">
              {create.isPending ? "添加中…" : "添加"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        {providersFailed && (
          <p className="text-sm text-red-500">
            {providersError instanceof Error ? providersError.message : String(providersError)}
          </p>
        )}
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

import { Library } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Input } from "@/components/ui/input";

export function VoicesPage() {
  const queryClient = useQueryClient();
  const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.listVoices });

  const [name, setName] = useState("");
  const [voiceId, setVoiceId] = useState("");
  const [refText, setRefText] = useState("");
  const [tags, setTags] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["voices"] });

  const create = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("name", name);
      if (voiceId) form.set("voice_id", voiceId);
      if (refText) form.set("ref_text", refText);
      if (tags) form.set("tags", tags);
      if (file) form.set("file", file);
      return api.createVoice(form);
    },
    onSuccess: () => {
      setName("");
      setVoiceId("");
      setRefText("");
      setTags("");
      setFile(null);
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err.message),
  });

  const setDefault = useMutation({
    mutationFn: (id: number) => api.setDefaultVoice(id),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteVoice(id),
    onSuccess: invalidate,
  });

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader kind="voices" icon={Library} title="音色库" description="保存参考音频，或登记云端复刻返回的音色。" />
      <Card>
        <CardHeader>
          <CardTitle>添加音色</CardTitle>
          <CardDescription>保存参考音频与文本，或登记云端复刻返回的 voice_id。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="名称" hint="在合成和视频页的音色列表里显示这个名字。">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="voice_id" hint="云端克隆服务返回的音色编号才填。只用本地参考音频时留空，不要填 1 这种序号。">
              <Input
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
              />
            </Field>
            <Field label="标签" hint="逗号分隔，方便以后筛选，例如 男声,中文。">
              <Input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
              />
            </Field>
            <Field label="参考音频" hint="可选。上传一段清晰人声，供声音克隆使用。">
              <FileDrop
                accept="audio/*"
                title="点击或拖拽上传参考音频"
                subtitle="清晰人声，10 秒内为佳"
                names={file ? [file.name] : []}
                onSelect={(fs) => setFile(fs?.[0] ?? null)}
              />
            </Field>
          </div>
          <Field label="参考文本" hint="可选。填写参考音频里说的原话，克隆时更准确。">
            <Input
              value={refText}
              onChange={(e) => setRefText(e.target.value)}
            />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button className="w-fit" onClick={() => create.mutate()} disabled={!name || create.isPending}>
            添加
          </Button>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        {voices?.length === 0 && <p className="text-sm text-muted-foreground">还没有音色。</p>}
        {voices?.map((v) => (
          <Card key={v.id}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{v.name}</span>
                  {v.is_default && (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-xs">默认</span>
                  )}
                  {v.tags.map((t) => (
                    <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                      {t}
                    </span>
                  ))}
                </div>
                <div className="text-xs text-muted-foreground">
                  {v.voice_id ? `voice_id: ${v.voice_id}` : ""}
                  {v.ref_audio_path ? " · 含参考音频" : ""}
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => setDefault.mutate(v.id)} disabled={v.is_default}>
                <Star /> 设为默认
              </Button>
              <Button variant="ghost" size="icon" onClick={() => remove.mutate(v.id)} title="删除">
                <Trash2 />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

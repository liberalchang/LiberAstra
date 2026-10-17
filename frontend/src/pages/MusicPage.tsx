import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Music, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api, fetchBgmBlob } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { formatSize } from "@/lib/utils";

/** 单条音乐的试听播放器：带鉴权拉 blob 后交给 audio 标签。 */
function BgmPlayer({ name }: { name: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    setSrc(null);
    setFailed(false);
    fetchBgmBlob(name)
      .then((b) => {
        if (!alive) return;
        url = URL.createObjectURL(b);
        setSrc(url);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      // 组件卸载时 URL 已交给 audio；立即吊销即可（此时若正在播放会停止，可接受）
      if (url) URL.revokeObjectURL(url);
    };
  }, [name]);
  if (failed) return <span className="text-xs text-red-500">加载失败</span>;
  if (!src) return <span className="text-xs text-muted-foreground">加载中…</span>;
  return <audio controls preload="none" src={src} className="h-9 w-full" />;
}

/** 音乐库：背景音乐的上传（自动入库）、试听与删除。 */
export function MusicPage() {
  const queryClient = useQueryClient();
  const { data: items } = useQuery({ queryKey: ["bgm"], queryFn: api.listBgm });

  const [file, setFile] = useState<File | null>(null);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["bgm"] });

  const upload = useMutation({
    mutationFn: () => api.uploadBgm(file!),
    onSuccess: (item) => {
      setFeedback({ ok: true, message: `已入库：${item.name}` });
      setFile(null);
      invalidate();
    },
    onError: (err) => setFeedback({ ok: false, message: err.message }),
  });

  const remove = useMutation({
    mutationFn: (name: string) => api.deleteBgm(name),
    onSuccess: () => invalidate(),
  });

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader
        kind="music"
        icon={Music}
        title="音乐库"
        description="管理背景音乐：上传后自动入库，快速创作页可直接选用。同名文件自动加序号，不会覆盖。"
      />

      <Card>
        <CardHeader>
          <CardTitle>上传音乐</CardTitle>
          <CardDescription>支持 MP3 / WAV / M4A / OGG / FLAC / AAC，单个不超过 50MB。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Field label="音乐文件" hint="上传后即进入音乐库，全站可复用。">
            <FileDrop
              accept="audio/*"
              title="点击或拖拽上传音乐"
              subtitle="MP3 / WAV / M4A / OGG / FLAC / AAC"
              names={file ? [file.name] : []}
              onSelect={(fs) => setFile(fs?.[0] ?? null)}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Button onClick={() => upload.mutate()} disabled={!file || upload.isPending}>
              {upload.isPending ? "上传中…" : "上传"}
            </Button>
            {feedback && (
              <span className={`text-sm ${feedback.ok ? "text-green-600" : "text-red-500"}`}>
                {feedback.message}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        {items?.length === 0 && (
          <p className="text-sm text-muted-foreground">还没有音乐，先上传一首。</p>
        )}
        {items?.map((item) => (
          <Card key={item.name}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{item.name}</div>
                <div className="text-xs text-muted-foreground">{formatSize(item.size)}</div>
              </div>
              <div className="w-56 shrink-0">
                <BgmPlayer name={item.name} />
              </div>
              <Button
                variant="ghost"
                size="icon"
                title="删除"
                onClick={() => remove.mutate(item.name)}
                disabled={remove.isPending}
              >
                <Trash2 />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

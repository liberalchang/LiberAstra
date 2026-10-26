import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutTemplate, Trash2 } from "lucide-react";
import { useState } from "react";

import { api, type TemplateOut } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { TemplateThumb } from "@/components/TemplateThumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { FileDrop } from "@/components/ui/file-drop";
import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/utils";
import { useTx } from "@/i18n/tx";

const ASPECTS = [
  { value: "9:16", label: "9:16 竖屏" },
  { value: "1:1", label: "1:1 方形" },
  { value: "16:9", label: "16:9 横屏" },
];
const TYPE_FILTERS = [
  { value: "", label: "全部类型" },
  { value: "static", label: "静态样式" },
  { value: "image", label: "生成插图" },
  { value: "video", label: "生成视频" },
  { value: "asset", label: "素材模板" },
];

/** 分镜模板管理：画幅页签 + 类型筛选浏览、上传 HTML 模板、删除用户模板。 */
export function TemplatesPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.listTemplates(),
  });

  const [browseAspect, setBrowseAspect] = useState("9:16");
  const [typeFilter, setTypeFilter] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [file, setFile] = useState<File | null>(null);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["templates"] });

  const upload = useMutation({
    mutationFn: () => api.uploadTemplate(aspect, file!),
    onSuccess: (t) => {
      setFeedback({ ok: true, message: tx("已上传 {name}（{type}）", { name: t.name, type: tx(t.type_label) }) });
      setFile(null);
      invalidate();
    },
    onError: (err) => setFeedback({ ok: false, message: err.message }),
  });

  const remove = useMutation({
    mutationFn: (t: TemplateOut) => api.deleteTemplate(t.aspect, t.name),
    onSuccess: () => invalidate(),
  });

  const shown =
    templates?.filter(
      (t) => t.aspect === browseAspect && (!typeFilter || t.type === typeFilter),
    ) ?? [];

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader
        kind="templates"
        icon={LayoutTemplate}
        title={tx("模板管理")}
        description={tx("分镜模板决定快速创作的画面样式。模板是带 {{占位符}} 的 HTML 文件，文件名前缀标识类型。")}
      />

      <Card>
        <CardHeader>
          <CardTitle>{tx("上传模板")}</CardTitle>
          <CardDescription>
            {tx('文件名以 static_（静态样式）/ image_（生成插图）/ video_（生成视频）开头，例如 static_my_card.html。')}
            {tx('画布尺寸须与所选画幅一致（1080x1920 / 1080x1080 / 1920x1080）。')}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={tx("画幅")} hint={tx("模板会被放进对应画幅的目录。")}>
              <select className={selectClass} value={aspect} onChange={(e) => setAspect(e.target.value)}>
                {ASPECTS.map((a) => (
                  <option key={a.value} value={a.value}>{tx(a.label)}</option>
                ))}
              </select>
            </Field>
            <Field label={tx("模板文件")} hint={tx("单个 HTML 文件，不超过 1MB。")}>
              <FileDrop
                accept=".html,text/html"
                title={tx("点击或拖拽上传 HTML 模板")}
                subtitle={tx("static_ / image_ / video_ 开头")}
                names={file ? [file.name] : []}
                onSelect={(fs) => setFile(fs?.[0] ?? null)}
              />
            </Field>
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={() => upload.mutate()} disabled={!file || upload.isPending}>
              {upload.isPending ? tx("上传中…") : tx("上传")}
            </Button>
            {feedback && (
              <span className={`text-sm ${feedback.ok ? "text-success" : "text-danger"}`}>
                {feedback.message}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        <Segmented
          ariaLabel={tx("画幅")}
          options={ASPECTS.map((a) => ({ value: a.value, label: tx(a.label) }))}
          value={browseAspect}
          onChange={setBrowseAspect}
        />
        <div className="flex flex-wrap gap-1.5">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setTypeFilter(f.value)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs transition-colors",
                typeFilter === f.value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/70 hover:text-foreground",
              )}
            >
              {tx(f.label)}
            </button>
          ))}
        </div>
      </div>

      {templates && shown.length === 0 && (
        <p className="text-sm text-muted-foreground">{tx("该分类下没有模板，可以在上方上传。")}</p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {shown.map((t) => (
          <Card key={`${t.aspect}/${t.name}`} className="overflow-hidden">
            <TemplateThumb
              aspect={t.aspect}
              name={t.name}
              className={
                t.aspect === "16:9" ? "aspect-video w-full" : t.aspect === "1:1" ? "aspect-square w-full" : "aspect-[9/16] w-full"
              }
            />
            <CardContent className="flex items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{t.name}</div>
                <div className="text-xs text-muted-foreground">
                  {t.type_label} · {t.source === "builtin" ? tx("内置") : tx("用户上传")}
                </div>
              </div>
              {t.source === "user" && (
                <Button
                  variant="ghost"
                  size="icon"
                  title={tx("删除")}
                  onClick={() => remove.mutate(t)}
                  disabled={remove.isPending}
                >
                  <Trash2 />
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

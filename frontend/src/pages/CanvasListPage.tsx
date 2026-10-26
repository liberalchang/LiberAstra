/** 画布列表页：卡片网格 + 新建 / 复制 / 删除。画布即资源,点卡片进入编辑器继续编辑。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2, Waypoints } from "lucide-react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { api, type CanvasListOut } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { useTx } from "@/i18n/tx";

function CanvasCard({ canvas, onOpen, onDuplicate, onDelete }: {
  canvas: CanvasListOut;
  onOpen: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const tx = useTx();
  return (
    <div className="group rounded-xl border border-border bg-card p-4 transition-shadow hover:shadow-md">
      <button type="button" className="block w-full text-left" onClick={onOpen}>
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
            <Waypoints className="size-4" />
          </span>
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{canvas.name}</span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {tx("{n} 个节点", { n: canvas.node_count })} ·{" "}
          {new Date(canvas.updated_at).toLocaleString()}
        </p>
      </button>
      <div className="mt-3 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <Button variant="ghost" size="icon" className="size-7" title={tx("复制画布")} onClick={onDuplicate}>
          <Copy className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-7 text-danger"
          title={tx("删除画布")}
          onClick={onDelete}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

/** /canvas 入口：有最近编辑的画布就直接回编辑器（保留未保存状态）；?mode=list 强制列表。 */
export function CanvasEntryPage() {
  const [params] = useSearchParams();
  const last = localStorage.getItem("liberastra-canvas-last");
  if (!last || params.get("mode") === "list") return <CanvasListPage />;
  return <Navigate to={`/canvas/${last}`} replace />;
}

export function CanvasListPage() {
  const tx = useTx();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["canvases"], queryFn: api.listCanvases });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["canvases"] });

  const create = useMutation({
    mutationFn: () => api.createCanvas({}),
    onSuccess: (canvas) => {
      void invalidate();
      navigate(`/canvas/${canvas.id}`);
    },
  });
  const duplicate = useMutation({
    mutationFn: (id: string) => api.duplicateCanvas(id),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteCanvas(id),
    onSuccess: invalidate,
  });

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader
        kind="canvas"
        icon={Waypoints}
        title={tx("画布")}
        description={tx("把输入、生成与合成编排成可视化流程；节点结果可保存到资源库。")}
      />
      <div className="flex justify-end">
        <Button size="sm" onClick={() => create.mutate()} disabled={create.isPending}>
          <Plus className="size-4" />
          {tx("新建画布")}
        </Button>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">{tx("加载中…")}</p>
      ) : !data?.length ? (
        <div className="grid h-48 place-items-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
          {tx("还没有画布，点击右上角新建")}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.map((canvas) => (
            <CanvasCard
              key={canvas.id}
              canvas={canvas}
              onOpen={() => navigate(`/canvas/${canvas.id}`)}
              onDuplicate={() => duplicate.mutate(canvas.id)}
              onDelete={() => {
                if (window.confirm(tx("删除这张画布？节点执行记录会一并删除，已发布的资源不受影响。"))) {
                  remove.mutate(canvas.id);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

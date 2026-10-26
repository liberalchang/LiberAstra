/** 画布编辑器页：React Flow 无限画布 + 工具坞 + 右侧属性面板。
 *
 * 执行流：保存 → POST run（选中节点或其缺省=全部末端）→ 轮询 node_runs + 内存 plan
 * 合并进 store。刷新页面后 load 时发现 pending/running 节点会自动恢复轮询。
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
} from "@xyflow/react";
import { ChevronLeft, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "@xyflow/react/dist/style.css";

import { api, ApiError, type WorkflowPackOut } from "@/api/client";
import { applyPackToNode } from "@/canvas/applyPack";
import { layeredLayout } from "@/canvas/layout";
import { CanvasBottomBar, type CanvasTool } from "@/components/canvas/CanvasBottomBar";
import { CanvasDock } from "@/components/canvas/CanvasDock";
import { canvasEdgeTypes } from "@/components/canvas/CanvasEdge";
import { NodeInspector } from "@/components/canvas/NodeInspector";
import { canvasNodeTypes } from "@/components/canvas/nodes";
import { QuickAddMenu, type QuickAddPick } from "@/components/canvas/QuickAddMenu";
import { useCanvasUiStore } from "@/components/canvas/ui-state";
import { MediaLightbox } from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { useTx } from "@/i18n/tx";
import { useCanvasStore, nextVarName } from "@/stores/canvas";

/** ReactFlow 的 dark/light 跟随 <html> 的 dark class（与 Layout 主题开关同源）。 */
function useColorMode(): "dark" | "light" {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains("dark")),
    );
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return dark ? "dark" : "light";
}

interface QuickAddState {
  x: number;
  y: number;
  /** 连线落空时带上待接的源节点,建点后自动连线 */
  pendingFrom?: string;
}

function CanvasEditor({ canvasId }: { canvasId: string }) {
  const tx = useTx();
  const colorMode = useColorMode();
  const store = useCanvasStore();
  const queryClient = useQueryClient();
  const { screenToFlowPosition, flowToScreenPosition, fitView } = useReactFlow();
  const wrapRef = useRef<HTMLDivElement>(null);
  // 信号色从主题 token 读取,明暗主题切换时重算(小地图/状态点共用)
  const signal = useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const v = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
    const idle = v("--muted-foreground", "#52525b");
    return {
      danger: v("--danger", "#dc2626"),
      info: v("--info", "#2563eb"),
      warning: v("--warning", "#b45309"),
      success: v("--success", "#15803d"),
      idle,
      canceled: `color-mix(in srgb, ${idle} 55%, transparent)`,
    };
  }, [colorMode]);
  const [quickAdd, setQuickAdd] = useState<QuickAddState | null>(null);
  const [tool, setTool] = useState<CanvasTool>("hand");
  const [saving, setSaving] = useState(false);
  // 通知:sticky 的错误不自动消失;计时器可清理,连续 flash 不互踩
  const [notice, setNotice] = useState<{ text: string; sticky: boolean } | null>(null);
  const flashTimer = useRef<number | null>(null);
  const [exitAsk, setExitAsk] = useState(false);
  const navigate = useNavigate();
  const preview = useCanvasUiStore((s) => s.preview);
  const setPreview = useCanvasUiStore((s) => s.setPreview);
  const addAfter = useCanvasUiStore((s) => s.addAfter);

  // 节点 + 钮点击:在源节点右侧弹快速建点,建完自动连线
  useEffect(() => {
    if (!addAfter) return;
    const node = useCanvasStore.getState().nodes.find((n) => n.id === addAfter);
    if (node) {
      const screen = flowToScreenPosition({
        x: node.position.x + 300,
        y: node.position.y + 30,
      });
      openQuickAdd(screen.x, screen.y, addAfter);
    }
    useCanvasUiStore.getState().requestAddAfter(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addAfter]);

  const selectedNode = store.nodes.find((n) => n.selected) ?? null;

  const flash = (text: string, opts?: { sticky?: boolean }) => {
    if (flashTimer.current != null) window.clearTimeout(flashTimer.current);
    const sticky = Boolean(opts?.sticky);
    setNotice({ text, sticky });
    if (!sticky) {
      flashTimer.current = window.setTimeout(() => setNotice(null), 3200);
    }
  };
  useEffect(
    () => () => {
      if (flashTimer.current != null) window.clearTimeout(flashTimer.current);
    },
    [],
  );

  // Ctrl+Z 撤销 / Ctrl+Shift+Z 或 Ctrl+Y 重做(输入控件内不拦截,留给文本自身)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      if (!(e.ctrlKey || e.metaKey)) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        useCanvasStore.getState().undo();
      } else if (key === "y" || (key === "z" && e.shiftKey)) {
        e.preventDefault();
        useCanvasStore.getState().redo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const save = useCallback(async (): Promise<boolean> => {
    const s = useCanvasStore.getState();
    setSaving(true);
    try {
      const saved = await api.updateCanvas(canvasId, {
        name: s.name.trim() || "未命名画布",
        graph: s.serialize(),
      });
      // 关键：保存结果直接写回查询缓存,否则重进画布会先读到保存前的旧图
      queryClient.setQueryData(["canvas", canvasId], saved);
      useCanvasStore.setState({ dirty: false });
      return true;
    } catch (err) {
      flash(err instanceof Error ? err.message : tx("保存失败"), { sticky: true });
      return false;
    } finally {
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvasId]);

  // 双击空白处弹快速建点：React Flow 的 d3-zoom 在目标阶段拦截 dblclick(双击缩放),
  // 所以关掉双击缩放,并用捕获阶段监听确保先到。
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const handler = (e: MouseEvent) => {
      if ((e.target as HTMLElement).closest(".react-flow__node")) return;
      if (!(e.target as HTMLElement).closest(".react-flow__pane")) return;
      openQuickAdd(e.clientX, e.clientY);
    };
    wrap.addEventListener("dblclick", handler, true);
    return () => wrap.removeEventListener("dblclick", handler, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ctrl+S 保存
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        void save();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [save]);

  // 执行状态轮询：runActive 期间每 1.5s 拉一次详情 + 实时 plan。
  // 递归 setTimeout + 在途标志:慢网时不会出现并发重叠与乱序覆盖。
  useEffect(() => {
    if (!store.runActive) return;
    let stopped = false;
    let timer: number | undefined;
    const tick = async () => {
      try {
        const [detail, runs] = await Promise.all([
          api.getCanvas(canvasId),
          api.getCanvasRuns(canvasId),
        ]);
        if (!stopped) useCanvasStore.getState().applyRuns(detail.node_runs, runs.plan);
      } catch {
        /* 网络抖动下一拍再试 */
      }
      if (!stopped) timer = window.setTimeout(tick, 1500);
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [store.runActive, canvasId]);

  /** 退出到画布列表：有未保存修改时先问。 */
  const requestExit = () => {
    if (useCanvasStore.getState().dirty) setExitAsk(true);
    else navigate("/canvas?mode=list");
  };
  const exitDiscard = () => {
    // 用户选择不保存：清掉内存态,下次进画布从服务端重新加载
    useCanvasStore.getState().reset();
    navigate("/canvas?mode=list");
  };
  const exitSave = async () => {
    if (await save()) navigate("/canvas?mode=list");
  };

  /** 保存并执行指定节点(空数组 = 当前选中,或缺省全部末端)。 */
  const runNodes = useCallback(
    async (nodeIds: string[]) => {
      const s = useCanvasStore.getState();
      if (s.nodes.length === 0) {
        flash(tx("画布为空，先双击画布添加节点"));
        return;
      }
      if (!(await save())) return;
      try {
        const result = await api.runCanvas(canvasId, { node_ids: nodeIds });
        useCanvasStore.getState().applyRuns(
          [],
          result.plan.map((p) => ({
            node_id: p.node_id,
            status: p.status,
            job_id: p.job_id,
            reused: p.reused,
          })),
        );
        useCanvasStore.getState().setRunActive(true);
      } catch (err) {
        flash(err instanceof Error ? err.message : tx("执行失败"), { sticky: true });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [canvasId, save],
  );

  const run = () => {
    const s = useCanvasStore.getState();
    const targets = s.nodes.filter((n) => n.selected).map((n) => n.id);
    void runNodes(targets);
  };

  // 节点卡上的「重试」:保存后单独重跑该节点
  const retryNode = useCanvasUiStore((s) => s.retryNode);
  useEffect(() => {
    if (!retryNode) return;
    useCanvasUiStore.getState().requestRetry(null);
    void runNodes([retryNode]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryNode]);

  const layout = () => {
    const s = useCanvasStore.getState();
    s.applyLayout(layeredLayout(s.nodes, s.edges));
    window.setTimeout(() => void fitView({ padding: 0.2 }), 50);
  };

  const openQuickAdd = (clientX: number, clientY: number, pendingFrom?: string) => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    // 菜单限制在画布框内(宽 240 + 高约 320),避免贴边时超出画布区域
    const x = Math.max(8, Math.min(clientX - rect.left, rect.width - 248));
    const y = Math.max(8, Math.min(clientY - rect.top, rect.height - 330));
    setQuickAdd({ x, y, pendingFrom });
  };

  const pickQuickAdd = (pick: QuickAddPick) => {
    if (!quickAdd) return;
    const rect = wrapRef.current?.getBoundingClientRect();
    const position = screenToFlowPosition({
      x: quickAdd.x + (rect?.left ?? 0),
      y: quickAdd.y + (rect?.top ?? 0),
    });
    // 快速建点 = 一步撤销:建点、语音模式修正、选包补建、自动连线合并为一个历史条目
    store.batch(() => {
      const node = store.addNode(pick.kind, pick.mediaKind, position);
      // 语音节点:asr 模式在建点后写入,变量名同步改为 output_text_n
      if (pick.kind === "speech" && pick.speechMode === "asr") {
        store.updateNodeData(node.id, {
          mode: "asr",
          varName: nextVarName(store.nodes, "output_text"),
        });
      }
      // 功能节点带所属:默认加载组内第一个包(并自动补建必填输入)
      if (pick.kind === "function" && pick.group) {
        store.updateNodeData(node.id, { group: pick.group });
        const groups = queryClient.getQueryData<Record<string, string[]>>(["canvas-groups"]);
        const packs = queryClient.getQueryData<WorkflowPackOut[]>(["workflows"]);
        const firstName = groups?.[pick.group]?.[0];
        const pack = firstName ? packs?.find((p) => p.name === firstName) : undefined;
        if (pack) {
          const created = applyPackToNode(node.id, pack, {});
          if (created > 0) flash(tx("已自动补建 {n} 个必填输入节点", { n: created }));
        }
      }
      if (quickAdd.pendingFrom) {
        store.onConnect({
          source: quickAdd.pendingFrom,
          target: node.id,
          sourceHandle: `out-${quickAdd.pendingFrom}`,
          targetHandle: `in-${node.id}`,
        });
      }
    });
    setQuickAdd(null);
  };

  return (
    <div ref={wrapRef} className="relative h-full w-full overflow-hidden rounded-2xl border border-border">
      <ReactFlow
        nodes={store.nodes}
        edges={store.edges}
        nodeTypes={canvasNodeTypes}
        edgeTypes={canvasEdgeTypes}
        onNodesChange={store.onNodesChange}
        onEdgesChange={store.onEdgesChange}
        onConnect={(conn: Connection) => {
          const rejected = store.onConnect(conn);
          if (rejected === "cycle") flash(tx("不能形成环形依赖"));
          else if (rejected === "duplicate") flash(tx("两个节点已连接"));
          else if (rejected === "concat-kind") flash(tx("合成节点只接受同类型媒体"));
          else if (rejected === "input-no-inlet") flash(tx("输入节点不能接受连线"));
        }}
        onConnectEnd={(event, connectionState) => {
          // 连线落空：在落点弹快速建点，选中后自动接上
          if (connectionState.isValid) return;
          const from = connectionState.fromNode?.id;
          if (!from) return;
          const { clientX, clientY } = event as unknown as MouseEvent;
          openQuickAdd(clientX, clientY, from);
        }}
        onMoveEnd={(_e, vp) => store.setViewport(vp)}
        defaultViewport={store.viewport}
        colorMode={colorMode}
        minZoom={0.25}
        maxZoom={1.8}
        panOnDrag={tool === "hand" ? true : [1, 2]}
        selectionOnDrag={tool === "select"}
        zoomOnDoubleClick={false}
        deleteKeyCode={["Backspace", "Delete"]}
        fitView={store.nodes.length === 0}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.5} />
        <MiniMap
          pannable
          zoomable
          className="!bg-card"
          nodeColor={(n) => {
            const status = (n.data as { run?: { status?: string } } | undefined)?.run?.status;
            // 信号灯规则:颜色读主题 token,运行=信号蓝(紫只留给动作),取消用空心感的中性调
            return status === "failed"
              ? signal.danger
              : status === "running"
                ? signal.info
                : status === "pending"
                  ? signal.warning
                  : status === "succeeded"
                    ? signal.success
                    : status === "canceled"
                      ? signal.canceled
                      : signal.idle;
          }}
        />
        <Controls showInteractive={false} />
        <Panel position="top-left">
          <Button
            variant="outline"
            size="sm"
            className="bg-card/95"
            onClick={requestExit}
            title={tx("退出到画布列表")}
          >
            <ChevronLeft className="size-4" />
            {tx("退出")}
          </Button>
        </Panel>
        <CanvasDock
          saving={saving}
          running={store.runActive}
          onSave={() => void save()}
          onRun={() => void run()}
        />
        <CanvasBottomBar
          tool={tool}
          onToolChange={setTool}
          onAdd={() => {
            const rect = wrapRef.current?.getBoundingClientRect();
            if (rect) openQuickAdd(rect.left + rect.width / 2, rect.top + rect.height / 2);
          }}
          onLayout={layout}
        />
        {store.nodes.length === 0 && !quickAdd && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <p className="rounded-xl border border-dashed border-border bg-card/60 px-4 py-2 text-sm text-muted-foreground">
              {tx("双击画布或点下方 + 添加节点；拖动节点右侧圆点连线")}
            </p>
          </div>
        )}
        {notice && (
          <div
            role="status"
            aria-live="polite"
            className="absolute left-1/2 top-4 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm shadow-lg"
          >
            {notice.text}
            {notice.sticky && (
              <button
                type="button"
                className="grid size-6 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label={tx("关闭通知")}
                onClick={() => setNotice(null)}
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
        )}
        {quickAdd && (
          <QuickAddMenu
            x={quickAdd.x}
            y={quickAdd.y}
            onPick={pickQuickAdd}
            onClose={() => setQuickAdd(null)}
          />
        )}
      </ReactFlow>
      <NodeInspector
        node={selectedNode}
        canvasId={canvasId}
        onRequestSave={save}
        onFlash={flash}
      />
      {exitAsk && (
        <LightboxShell onClose={() => setExitAsk(false)} ariaLabel={tx("退出确认")} className="max-w-xs">
          <div className="flex flex-col gap-3 p-4">
            <p className="text-sm">{tx("画布有未保存的修改，退出前是否保存？")}</p>
            <div className="flex flex-col gap-1.5">
              <Button size="sm" onClick={() => void exitSave()} disabled={saving}>
                {tx("保存并退出")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-danger/40 text-danger hover:bg-danger/10"
                onClick={exitDiscard}
              >
                {tx("不保存退出")}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExitAsk(false)}>
                {tx("取消")}
              </Button>
            </div>
          </div>
        </LightboxShell>
      )}
      <MediaLightbox target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

export function CanvasPage() {
  const { id } = useParams<{ id: string }>();
  const tx = useTx();
  const navigate = useNavigate();
  const loaded = useCanvasStore((s) => s.canvasId === id);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["canvas", id],
    queryFn: () => api.getCanvas(id!),
    enabled: Boolean(id),
    staleTime: 0,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  // 记录最近编辑的画布:从导航「画布」进入时直接回到这里(见 CanvasEntryPage)
  useEffect(() => {
    if (id) localStorage.setItem("liberastra-canvas-last", id);
  }, [id]);

  // 画布不存在(如已删除/换了数据库):清掉失效的「最近画布」并回落到列表
  useEffect(() => {
    if (isError && error instanceof ApiError && error.status === 404) {
      if (localStorage.getItem("liberastra-canvas-last") === id) {
        localStorage.removeItem("liberastra-canvas-last");
      }
      navigate("/canvas?mode=list", { replace: true });
    }
  }, [isError, error, id, navigate]);

  useEffect(() => {
    if (data && useCanvasStore.getState().canvasId !== data.id) {
      useCanvasStore.getState().load(data);
    }
  }, [data]);

  // 注意:不在卸载时清空 store——切到别的功能页再回「画布」时,未保存的编辑与视口状态保留

  if (!id) return null;
  if (isLoading || !loaded) {
    return (
      <div className="grid h-64 place-items-center text-sm text-muted-foreground">
        {tx("加载画布…")}
      </div>
    );
  }
  if (isError) {
    return (
      <div className="grid h-64 place-items-center gap-2 text-sm">
        <p className="text-danger">{tx("画布加载失败")}</p>
        <a href="/canvas?mode=list" className="text-primary underline">
          {tx("返回画布列表")}
        </a>
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <CanvasEditor canvasId={id} />
    </ReactFlowProvider>
  );
}

/** 导演台：左侧悬浮对话面板，会话、技能、模型、附件、`@` 节点引用与画布工具确认。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AudioLines,
  Ban,
  Bot,
  Check,
  ChevronDown,
  Cpu,
  EyeOff,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Loader2,
  Maximize2,
  PanelLeftClose,
  Plus,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Video,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  api,
  ApiError,
  type AgentAttachment,
  type AgentMessageOut,
  type AgentRef,
  type AgentSessionOut,
  type AgentSkillFileOut,
  type AgentSkillOut,
  type AgentSseEvent,
  type AssetOut,
  type ModelItem,
  type ProviderOut,
} from "@/api/client";
import {
  collectRefOptions,
  nodeHandle,
  refForNode,
  resolveRefs,
  type RefOption,
} from "@/canvas/refs";
import { MarkdownView } from "@/components/MarkdownView";
import { MediaThumb } from "@/components/MediaLightbox";
import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { useCanvasUiStore } from "@/components/canvas/ui-state";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";
import {
  executeClientTool,
  type ClientToolCall,
  type ClientToolResult,
} from "@/director/clientTools";
import { useCanvasStore } from "@/stores/canvas";

type LiveItem =
  | { kind: "user"; text: string; attachments: AgentAttachment[]; refs: AgentRef[] }
  | { kind: "assistant"; text: string }
  | {
      kind: "tool";
      id: string;
      name: string;
      args: string;
      status: "running" | "done" | "error";
      result?: unknown;
    }
  | { kind: "ask"; question: string; options: string[] };

interface ToolCallContent {
  id?: string;
  function?: { name?: string; arguments?: string };
}

const PANEL_WIDTH = 420;
const FOLLOW_DEFAULT = "__follow_default__";

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function toolName(call: ToolCallContent): string {
  return call.function?.name ?? "工具";
}

function outputsOf(result: unknown): { asset_id: number; kind: string }[] {
  if (!result || typeof result !== "object") return [];
  const outputs = (result as { outputs?: unknown }).outputs;
  if (!Array.isArray(outputs)) return [];
  return outputs
    .filter(
      (item): item is { asset_id: number; kind: string } =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as { asset_id?: unknown }).asset_id === "number",
    )
    .map((item) => ({ asset_id: item.asset_id, kind: item.kind || "image" }));
}

function ResultAssets({ result }: { result: unknown }) {
  const setPreview = useCanvasUiStore((s) => s.setPreview);
  const assets = outputsOf(result);
  if (!assets.length) return null;
  return (
    <div className="mt-1.5 grid grid-cols-3 gap-1.5">
      {assets.map((asset) => (
        <button
          key={`${asset.kind}-${asset.asset_id}`}
          type="button"
          className="overflow-hidden rounded-md border border-border"
          onClick={() => setPreview({ id: asset.asset_id, kind: asset.kind })}
        >
          <MediaThumb
            assetId={asset.asset_id}
            kind={asset.kind}
            className="aspect-square w-full object-cover"
          />
        </button>
      ))}
    </div>
  );
}

function ToolCard({
  name,
  args,
  status,
  result,
}: {
  name: string;
  args: string;
  status: "running" | "done" | "error";
  result?: unknown;
}) {
  const summary = (() => {
    try {
      const parsed = JSON.parse(args || "{}");
      return JSON.stringify(parsed).slice(0, 120);
    } catch {
      return args.slice(0, 120);
    }
  })();
  const resultText =
    result == null ? "" : typeof result === "string" ? result : JSON.stringify(result, null, 2);
  return (
    <details className="rounded-xl border border-border/80 bg-muted/25 px-2.5 py-2 text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-1.5">
        {status === "running" ? (
          <Loader2 className="size-3 animate-spin text-info" />
        ) : status === "error" ? (
          <Ban className="size-3 text-danger" />
        ) : (
          <Check className="size-3 text-success" />
        )}
        <span className="font-medium">{name}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">{summary}</span>
      </summary>
      {resultText && (
        <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-card p-1.5 text-[11px] text-muted-foreground">
          {resultText.slice(0, 4000)}
        </pre>
      )}
      <ResultAssets result={result} />
    </details>
  );
}

function UserBubble({
  text,
  attachments,
  refs,
}: {
  text: string;
  attachments: AgentAttachment[];
  refs: AgentRef[];
}) {
  const tx = useTx();
  return (
    <div className="ml-auto max-w-[88%] rounded-[18px] rounded-br-md bg-primary px-3.5 py-2.5 text-sm text-primary-foreground shadow-sm">
      {text && <p className="whitespace-pre-wrap leading-relaxed">{text}</p>}
      {(attachments.length > 0 || refs.length > 0) && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {attachments.map((item) => (
            <span
              key={`a-${item.asset_id}`}
              className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] text-primary-foreground/90"
            >
              {tx("附件")} #{item.asset_id} · {item.kind}
              {item.send_to_model === false ? ` · ${tx("仅节点")}` : ""}
            </span>
          ))}
          {refs.map((ref) => (
            <span
              key={`r-${ref.node_id}`}
              className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] text-primary-foreground/90"
            >
              @{ref.var_name || ref.title || ref.node_id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function PersistedMessages({
  messages,
  toolCallIds,
}: {
  messages: AgentMessageOut[];
  toolCallIds: Set<string>;
}) {
  return (
    <>
      {messages.map((message) => {
        const content = message.content as Record<string, unknown>;
        if (message.role === "user") {
          return (
            <UserBubble
              key={`m-${message.id}`}
              text={textOf(content.text)}
              attachments={(content.attachments as AgentAttachment[]) ?? []}
              refs={(content.refs as AgentRef[]) ?? []}
            />
          );
        }
        if (message.role === "assistant") {
          const text = textOf(content.text);
          const calls = (content.tool_calls as ToolCallContent[]) ?? [];
          return (
            <div key={`m-${message.id}`} className="space-y-1.5">
              {text && <MarkdownView source={text} />}
              {calls
                .filter((call) => !toolCallIds.has(String(call.id ?? "")))
                .map((call, index) => (
                  <ToolCard
                    key={`${message.id}-${index}`}
                    name={toolName(call)}
                    args={call.function?.arguments ?? "{}"}
                    status="done"
                  />
                ))}
            </div>
          );
        }
        if (message.role === "tool") {
          return (
            <ToolCard
              key={`m-${message.id}`}
              name={textOf(content.name) || "工具"}
              args="{}"
              status={content.ok === false ? "error" : "done"}
              result={content.result}
            />
          );
        }
        return null;
      })}
    </>
  );
}

export function DirectorPanel({
  canvasId,
  onFlash,
}: {
  canvasId: string;
  onFlash?: (text: string, opts?: { sticky?: boolean }) => void;
}) {
  const tx = useTx();
  const queryClient = useQueryClient();
  const nodes = useCanvasStore((s) => s.nodes);
  const directorRefNode = useCanvasUiStore((s) => s.directorRefNode);

  const [open, setOpen] = useState(() => loadJson<boolean>("liberastra-director-open", true));
  const [pos, setPos] = useState<{ x: number; y: number }>(() =>
    loadJson("liberastra-director-pos", { x: 12, y: 56 }),
  );
  const [currentId, setCurrentId] = useState<string | null>(() =>
    localStorage.getItem(`liberastra-director-session-${canvasId}`),
  );
  const [sessionOpen, setSessionOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [skillOpen, setSkillOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [pendingFileKind, setPendingFileKind] = useState("image");
  const [skillManageOpen, setSkillManageOpen] = useState(false);
  const [skillView, setSkillView] = useState<{
    name: string;
    body: string;
    license?: string;
    compatibility?: string;
    allowed_tools?: string[];
    files?: AgentSkillFileOut[];
  } | null>(null);
  const [assetOpen, setAssetOpen] = useState(false);
  const [assetKind, setAssetKind] = useState("image");
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [refs, setRefs] = useState<AgentRef[]>([]);
  const [refQuery, setRefQuery] = useState<{ start: number; text: string } | null>(null);
  const [refIndex, setRefIndex] = useState(0);
  const [selectedSkill, setSelectedSkill] = useState("");
  const [modelChoice, setModelChoice] = useState(FOLLOW_DEFAULT);
  const [live, setLive] = useState<LiveItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serverConfirm, setServerConfirm] = useState<
    { id: string; name: string; arguments: string; risk?: string; title?: string }[] | null
  >(null);
  const [clientConfirm, setClientConfirm] = useState<ClientToolCall[] | null>(null);

  const panelRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingClientRef = useRef<ClientToolCall[] | null>(null);
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["agent-sessions", canvasId],
    queryFn: () => api.listAgentSessions(canvasId),
  });
  const sessions = sessionsQuery.data ?? [];
  const session = sessions.find((item) => item.id === currentId) ?? null;

  const skillsQuery = useQuery({
    queryKey: ["agent-skills"],
    queryFn: api.listAgentSkills,
    staleTime: 30_000,
  });
  const skills = (skillsQuery.data ?? []).filter((item) => item.enabled);

  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const providers = providersQuery.data ?? [];

  const messagesQuery = useQuery({
    queryKey: ["agent-messages", currentId],
    queryFn: () => api.listAgentMessages(currentId!),
    enabled: Boolean(currentId),
    staleTime: 0,
  });
  const messages = messagesQuery.data ?? [];
  const toolCallIds = useMemo(
    () =>
      new Set(
        messages
          .filter((message) => message.role === "tool")
          .map((message) =>
            String((message.content as Record<string, unknown>).tool_call_id ?? ""),
          ),
      ),
    [messages],
  );

  const prefsQuery = useQuery({
    queryKey: ["system-preferences"],
    queryFn: api.getPreferences,
    staleTime: 60_000,
  });

  const llmOptions = useMemo(() => {
    const rows: {
      value: string;
      label: string;
      provider: string;
      model: string;
      vision: boolean;
      tools: boolean;
    }[] = [];
    for (const provider of providers as ProviderOut[]) {
      const catalog = (provider.extra?.model_catalog as ModelItem[] | undefined) ?? [];
      for (const model of catalog) {
        if (model.category !== "llm" || !model.enabled) continue;
        rows.push({
          value: `${provider.id}|${model.id}`,
          label: `${provider.name} · ${model.label || model.id}`,
          provider: provider.name,
          model: model.label || model.id,
          vision: model.sub_capabilities.includes("vision"),
          tools: model.sub_capabilities.includes("tools"),
        });
      }
    }
    return rows;
  }, [providers]);

  const systemDefault = useMemo(() => {
    const prefs = prefsQuery.data;
    const llmProviders = (providers as ProviderOut[]).filter((provider) => {
      const catalog = (provider.extra?.model_catalog as ModelItem[] | undefined) ?? [];
      return catalog.some((model) => model.category === "llm" && model.enabled);
    });
    const preferred = prefs?.default_llm_provider_id
      ? llmProviders.find((provider) => provider.id === prefs.default_llm_provider_id)
      : undefined;
    const provider = preferred ?? llmProviders[0];
    if (!provider) return null;
    const catalog = (provider.extra?.model_catalog as ModelItem[] | undefined) ?? [];
    const extra = (provider.extra ?? {}) as Record<string, unknown>;
    const extraModel = typeof extra.model === "string" ? extra.model.trim() : "";
    const model =
      prefs?.default_llm_model?.trim() ||
      extraModel ||
      provider.models[0] ||
      catalog.find((item) => item.category === "llm" && item.enabled)?.id ||
      "";
    const item = catalog.find((entry) => entry.id === model);
    return {
      value: `${provider.id}|${model}`,
      label: `${provider.name} · ${model || "default"}`,
      provider: provider.name,
      model: model || "default",
      vision: Boolean(item?.sub_capabilities.includes("vision")),
      tools: Boolean(item?.sub_capabilities.includes("tools")),
    };
  }, [providers, prefsQuery.data]);

  useEffect(() => {
    if (!session) {
      setModelChoice(FOLLOW_DEFAULT);
      return;
    }
    const current = `${session.provider_id ?? 0}|${session.model ?? ""}`;
    setModelChoice(
      systemDefault && current === systemDefault.value ? FOLLOW_DEFAULT : current,
    );
  }, [session?.id, session?.provider_id, session?.model, systemDefault?.value]);

  useEffect(() => {
    if (!currentId) return;
    localStorage.setItem(`liberastra-director-session-${canvasId}`, currentId);
  }, [canvasId, currentId]);

  useEffect(() => {
    setSelectedSkill("");
  }, [currentId]);

  useEffect(() => {
    if (open) window.setTimeout(() => areaRef.current?.focus(), 30);
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [live, messages]);

  useEffect(() => {
    if (!sessionsQuery.data) return;
    if (currentId && !sessionsQuery.data.some((item) => item.id === currentId)) {
      setCurrentId(sessionsQuery.data[0]?.id ?? null);
    }
  }, [sessionsQuery.data, currentId]);

  const selectedModel = useMemo(() => {
    if (modelChoice === FOLLOW_DEFAULT) return systemDefault;
    return (
      llmOptions.find((item) => item.value === modelChoice) ??
      (session
        ? {
            value: `${session.provider_id ?? 0}|${session.model ?? ""}`,
            label: session.model || tx("跟随系统默认"),
            provider: "",
            model: session.model || "",
            vision: true,
            tools: true,
          }
        : null)
    );
  }, [llmOptions, modelChoice, systemDefault, session, tx]);
  const currentVision = selectedModel?.vision ?? true;

  const refOptions = useMemo(() => collectRefOptions(nodes), [nodes]);
  const filteredRefOptions = useMemo(() => {
    const query = refQuery?.text.toLowerCase() ?? "";
    if (!query) return refOptions;
    return refOptions.filter(
      (item) =>
        item.handle.toLowerCase().includes(query) ||
        item.title.toLowerCase().includes(query),
    );
  }, [refOptions, refQuery]);

  const hasMedia = attachments.some(
    (item) =>
      item.send_to_model !== false &&
      (item.kind === "image" || item.kind === "video"),
  );
  const visionBlocked = hasMedia && !currentVision;
  const refsHaveMedia = refs.some((ref) =>
    (ref.assets ?? []).some(
      (asset) => asset.kind === "image" || asset.kind === "video",
    ),
  );
  const refsMediaSkipped = refsHaveMedia && !currentVision;

  const activeSkill =
    skills.find((item) => item.name === (session?.active_skill || selectedSkill)) ??
    skills.find((item) => item.name === "director") ??
    null;

  const persistOpen = (next: boolean) => {
    setOpen(next);
    localStorage.setItem("liberastra-director-open", JSON.stringify(next));
  };

  useEffect(() => {
    if (!directorRefNode) return;
    const node = nodes.find((item) => item.id === directorRefNode);
    useCanvasUiStore.getState().requestDirectorRef(null);
    if (!node) return;
    if (!open) persistOpen(true);
    const handle = nodeHandle(node);
    setRefs((prev) =>
      prev.some((item) => item.node_id === node.id)
        ? prev
        : [...prev, refForNode(node)],
    );
    setInput((prev) =>
      prev.includes(`@${handle}`)
        ? prev
        : `${prev}${prev.trim() ? " " : ""}@${handle} `,
    );
    window.setTimeout(() => areaRef.current?.focus(), 60);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [directorRefNode]);

  const onHeaderPointerDown = (event: React.PointerEvent) => {
    if ((event.target as HTMLElement).closest("button, input")) return;
    const parent = (panelRef.current?.offsetParent as HTMLElement | null)?.getBoundingClientRect();
    if (!parent) return;
    dragRef.current = {
      dx: event.clientX - parent.left - pos.x,
      dy: event.clientY - parent.top - pos.y,
    };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };
  const onHeaderPointerMove = (event: React.PointerEvent) => {
    if (!dragRef.current) return;
    const parent = (panelRef.current?.offsetParent as HTMLElement | null)?.getBoundingClientRect();
    if (!parent) return;
    const x = Math.max(
      0,
      Math.min(parent.width - PANEL_WIDTH, event.clientX - parent.left - dragRef.current.dx),
    );
    const y = Math.max(
      0,
      Math.min(parent.height - 120, event.clientY - parent.top - dragRef.current.dy),
    );
    setPos({ x, y });
  };
  const onHeaderPointerUp = () => {
    if (!dragRef.current) return;
    dragRef.current = null;
    localStorage.setItem("liberastra-director-pos", JSON.stringify(pos));
  };

  const modelPayload = () => {
    if (modelChoice === FOLLOW_DEFAULT || !modelChoice.includes("|")) {
      return { providerId: undefined, model: "" };
    }
    const [raw, model] = modelChoice.split("|");
    const providerId = Number(raw);
    return {
      providerId: Number.isFinite(providerId) && providerId > 0 ? providerId : undefined,
      model: model ?? "",
    };
  };

  const ensureSession = async (): Promise<AgentSessionOut | null> => {
    if (session) return session;
    const { providerId, model } = modelPayload();
    try {
      const created = await api.createAgentSession({
        canvas_id: canvasId,
        provider_id: providerId,
        model,
        active_skill: activeSkill?.name ?? "",
      });
      setCurrentId(created.id);
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) => [
        created,
        ...(old ?? []),
      ]);
      return created;
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建会话失败");
      return null;
    }
  };

  const appendAssistant = (text: string) => {
    setLive((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      if (last && last.kind === "assistant") {
        copy[copy.length - 1] = { ...last, text: last.text + text };
      } else {
        copy.push({ kind: "assistant", text });
      }
      return copy;
    });
  };

  const updateTool = (
    id: string,
    patch: Partial<Extract<LiveItem, { kind: "tool" }>>,
  ) => {
    setLive((prev) =>
      prev.map((item) =>
        item.kind === "tool" && item.id === id ? { ...item, ...patch } : item,
      ),
    );
  };

  const handleEvent = (event: AgentSseEvent) => {
    const data = event.data as Record<string, unknown>;
    switch (event.event) {
      case "token":
        appendAssistant(textOf(data.text));
        break;
      case "tool_start": {
        const call = data as { id: string; name: string; arguments: string };
        setLive((prev) => [
          ...prev,
          {
            kind: "tool",
            id: call.id,
            name: call.name,
            args: call.arguments ?? "{}",
            status: "running",
          },
        ]);
        break;
      }
      case "tool_progress": {
        const jobId = textOf(data.job_id);
        if (jobId) {
          setLive((prev) =>
            prev.map((item) =>
              item.kind === "tool" && item.status === "running"
                ? {
                    ...item,
                    result: { ...(item.result as object | undefined), job_id: jobId },
                  }
                : item,
            ),
          );
        }
        break;
      }
      case "tool_end": {
        const call = data as { id: string; ok?: boolean; result?: unknown };
        updateTool(call.id, {
          status: call.ok === false ? "error" : "done",
          result: call.result,
        });
        break;
      }
      case "ask_user":
        setLive((prev) => [
          ...prev,
          {
            kind: "ask",
            question: textOf(data.question),
            options: Array.isArray(data.options) ? data.options.map(String) : [],
          },
        ]);
        break;
      case "confirm":
        setServerConfirm(
          (data.calls as { id: string; name: string; arguments: string }[]) ?? [],
        );
        break;
      case "client_tool_request": {
        const calls = (data.calls as ClientToolCall[]) ?? [];
        pendingClientRef.current = calls;
        setLive((prev) => [
          ...prev,
          ...calls.map((call) => ({
            kind: "tool" as const,
            id: call.id,
            name: call.name,
            args: call.arguments,
            status: "running" as const,
          })),
        ]);
        break;
      }
      default:
        break;
    }
  };

  const afterStream = async (active: AgentSessionOut) => {
    const pending = pendingClientRef.current;
    pendingClientRef.current = null;
    if (!pending) return;
    if (pending.some((call) => call.requires_confirm)) {
      setClientConfirm(pending);
      return;
    }
    await executeAndContinue(active, pending);
  };

  const executeAndContinue = async (
    active: AgentSessionOut,
    calls: ClientToolCall[],
    remember = false,
    forceOverride?: boolean,
  ) => {
    setClientConfirm(null);
    const results: ClientToolResult[] = [];
    for (const call of calls) {
      updateTool(call.id, { status: "running" });
      let result: ClientToolResult;
      const effective =
        call.name === "canvas_run_nodes" && forceOverride !== undefined
          ? {
              ...call,
              args: { ...(call.args ?? {}), force: forceOverride },
            }
          : call;
      try {
        result = await executeClientTool(effective, {
          canvasId,
          queryClient,
          onFlash,
        });
      } catch (err) {
        result = {
          tool_call_id: call.id,
          name: call.name,
          result: {
            error: err instanceof Error ? err.message : "画布工具执行失败",
          },
        };
      }
      results.push(result);
      updateTool(call.id, {
        status: result.result?.error ? "error" : "done",
        result: result.result,
      });
    }
    abortRef.current = new AbortController();
    setStreaming(true);
    try {
      await api.agentToolResults(
        active.id,
        { results: results as unknown as Record<string, unknown>[], remember },
        handleEvent,
        abortRef.current.signal,
      );
      await afterStream(active);
    } catch (err) {
      setError(err instanceof Error ? err.message : "工具结果提交失败");
    } finally {
      setStreaming(false);
    }
  };

  const markAllNodeOnly = () => {
    setAttachments((prev) =>
      prev.map((item) =>
        item.kind === "image" || item.kind === "video"
          ? { ...item, send_to_model: false }
          : item,
      ),
    );
    setError(null);
  };

  const sendMessage = async (
    text: string,
    sendAttachments: AgentAttachment[] = [],
    sendRefs: AgentRef[] = [],
  ) => {
    if (streaming) return;
    if (!text.trim() && !sendAttachments.length && !sendRefs.length) return;
    if (serverConfirm || clientConfirm) {
      setError(tx("请先处理上面的确认卡片。"));
      return;
    }
    if (visionBlocked) {
      setError(tx("当前模型没有视觉能力，请换模型、把附件设为「仅节点」，或去掉图片/视频。"));
      return;
    }
    setError(null);
    const active = await ensureSession();
    if (!active) return;
    await messagesQuery.refetch();
    setLive([
      { kind: "user", text, attachments: sendAttachments, refs: sendRefs },
      { kind: "assistant", text: "" },
    ]);
    setInput("");
    setAttachments([]);
    setRefs([]);
    setRefQuery(null);
    pendingClientRef.current = null;
    setStreaming(true);
    abortRef.current = new AbortController();
    const { providerId, model } = modelPayload();
    try {
      await api.agentTurn(
        active.id,
        {
          text,
          attachments: sendAttachments,
          refs: sendRefs,
          provider_id: providerId ?? null,
          model,
          active_skill: activeSkill?.name ?? null,
        },
        handleEvent,
        abortRef.current.signal,
      );
      await afterStream(active);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "发送失败",
        );
      }
    } finally {
      setStreaming(false);
      void queryClient.invalidateQueries({ queryKey: ["agent-sessions", canvasId] });
    }
  };

  const send = () => {
    const finalRefs = resolveRefs(input, refOptions, nodes, refs);
    void sendMessage(input, attachments, finalRefs);
  };

  const stopStreaming = () => {
    const id = session?.id ?? currentId;
    if (id) void api.cancelAgentTurn(id).catch(() => undefined);
    abortRef.current?.abort();
  };

  const approveServerConfirm = async (approved: boolean, remember = false) => {
    if (!serverConfirm) return;
    const active = session ?? (await ensureSession());
    setServerConfirm(null);
    if (!active) return;
    setStreaming(true);
    abortRef.current = new AbortController();
    try {
      await api.agentToolResults(
        active.id,
        { results: [], approved, remember },
        handleEvent,
        abortRef.current.signal,
      );
      await afterStream(active);
    } catch (err) {
      setError(err instanceof Error ? err.message : "确认提交失败");
    } finally {
      setStreaming(false);
    }
  };

  const rejectClientCalls = async () => {
    if (!clientConfirm) return;
    const active = session ?? (await ensureSession());
    const calls = clientConfirm;
    setClientConfirm(null);
    if (!active) return;
    const results = calls.map((call) => ({
      tool_call_id: call.id,
      name: call.name,
      result: { error: "用户拒绝了该操作" },
    }));
    setStreaming(true);
    abortRef.current = new AbortController();
    try {
      await api.agentToolResults(
        active.id,
        {
          results: results as unknown as Record<string, unknown>[],
          approved: false,
        },
        handleEvent,
        abortRef.current.signal,
      );
      await afterStream(active);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setStreaming(false);
    }
  };

  const changeModel = async (value: string) => {
    setModelChoice(value);
    setModelOpen(false);
    if (!session) return;
    try {
      let updated: AgentSessionOut;
      if (value === FOLLOW_DEFAULT) {
        updated = await api.patchAgentSession(session.id, { use_default: true });
      } else {
        const [providerRaw, model] = value.split("|");
        updated = await api.patchAgentSession(session.id, {
          provider_id: Number(providerRaw),
          model: model ?? "",
        });
      }
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) =>
        (old ?? []).map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "切换模型失败");
    }
  };

  const chooseSkill = async (name: string) => {
    setSkillOpen(false);
    setSelectedSkill(name);
    if (!session) return;
    try {
      const updated = await api.patchAgentSession(session.id, { active_skill: name });
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) =>
        (old ?? []).map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "切换技能失败");
    }
  };

  const createSession = async () => {
    const { providerId, model } = modelPayload();
    try {
      const created = await api.createAgentSession({
        canvas_id: canvasId,
        provider_id: providerId,
        model,
        active_skill: activeSkill?.name ?? "",
      });
      setCurrentId(created.id);
      setLive([]);
      setServerConfirm(null);
      setClientConfirm(null);
      setSessionOpen(false);
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) => [
        created,
        ...(old ?? []),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "新建会话失败");
    }
  };

  const commitTitle = async () => {
    if (!renaming) return;
    setRenaming(false);
    if (!session) return;
    const title = titleDraft.trim();
    if (!title || title === session.title) return;
    try {
      const updated = await api.patchAgentSession(session.id, { title });
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) =>
        (old ?? []).map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改名称失败");
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await api.deleteAgentSession(id);
      queryClient.setQueryData<AgentSessionOut[]>(["agent-sessions", canvasId], (old) =>
        (old ?? []).filter((item) => item.id !== id),
      );
      if (currentId === id) {
        setCurrentId(null);
        setLive([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除会话失败");
    }
  };

  const onInputChange = (value: string, caret: number) => {
    setInput(value);
    const before = value.slice(0, caret);
    const match = /(^|[\s(])([/@])([^\s@/]*)$/.exec(before);
    if (match) {
      setRefQuery({
        start: before.length - match[2].length - match[3].length,
        text: match[3],
      });
      setRefIndex(0);
    } else {
      setRefQuery(null);
    }
  };

  const pickRef = (option: RefOption) => {
    if (!refQuery) return;
    const before = input.slice(0, refQuery.start);
    const after = input.slice(refQuery.start + 1 + refQuery.text.length);
    setInput(`${before}@${option.handle} ${after}`);
    setRefs((prev) =>
      prev.some((item) => item.node_id === option.nodeId)
        ? prev
        : [...prev, refForOption(option)],
    );
    setRefQuery(null);
    window.setTimeout(() => areaRef.current?.focus(), 20);
  };

  const refForOption = (option: RefOption): AgentRef => {
    const node = nodes.find((item) => item.id === option.nodeId);
    if (!node) {
      return { node_id: option.nodeId, var_name: option.handle, title: option.title };
    }
    return {
      node_id: node.id,
      var_name: option.handle,
      title: option.title,
      kind: option.kind,
      assets: node.data.run.assetIds.map((assetId) => ({
        asset_id: assetId,
        kind: option.kind,
      })),
      asset_ids: node.data.run.assetIds,
      text:
        node.data.kind === "input" && node.data.mediaKind === "text"
          ? node.data.text?.slice(0, 20_000)
          : undefined,
    };
  };

  const uploadAttachments = async (files: FileList | null, forcedKind?: string) => {
    if (!files) return;
    const next: AgentAttachment[] = [];
    for (const file of Array.from(files)) {
      const kind = file.type.startsWith("image/")
        ? "image"
        : file.type.startsWith("video/")
          ? "video"
          : file.type.startsWith("audio/")
            ? "audio"
            : file.type.startsWith("text/") || file.type === "application/json"
              ? "text"
              : forcedKind || "text";
      try {
        const result = await api.uploadFileAsAsset(file, kind, true);
        next.push({ asset_id: result.asset_id, kind, name: file.name, send_to_model: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "上传失败");
      }
    }
    if (next.length) setAttachments((prev) => [...prev, ...next]);
    if (fileRef.current) fileRef.current.value = "";
  };

  const addAssetAttachment = (asset: AssetOut) => {
    setAttachments((prev) =>
      prev.some((item) => item.asset_id === asset.id)
        ? prev
        : [...prev, { asset_id: asset.id, kind: asset.kind, name: asset.path, send_to_model: true }],
    );
    setAssetOpen(false);
  };

  if (!open) {
    return (
      <div className="absolute bottom-3 left-3 z-30 flex w-[420px] max-w-[calc(100%-24px)] items-center gap-2 rounded-2xl border border-border/80 bg-card/95 px-2.5 py-2 shadow-xl backdrop-blur-xl">
        <Bot className="size-4 shrink-0 text-primary" />
        <span className="shrink-0 text-sm font-medium">{tx("导演台")}</span>
        <input
          className="min-w-0 flex-1 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs outline-none placeholder:text-muted-foreground"
          placeholder={tx("问我怎么搭这张画布…")}
          onFocus={() => persistOpen(true)}
        />
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={() => persistOpen(true)}
          aria-label={tx("展开")}
        >
          <Maximize2 className="size-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <>
      <div
        ref={panelRef}
        className="absolute z-30 flex flex-col overflow-hidden rounded-[22px] border border-border/80 bg-card/95 shadow-2xl backdrop-blur-xl"
        style={{
          left: pos.x,
          top: pos.y,
          width: PANEL_WIDTH,
          height: `calc(100% - ${pos.y + 12}px)`,
        }}
      >
        {(sessionOpen || skillOpen || modelOpen || attachOpen) && (
          <button
            type="button"
            className="absolute inset-0 z-20 cursor-default"
            aria-label={tx("关闭菜单")}
            onClick={() => {
              setSessionOpen(false);
              setSkillOpen(false);
              setModelOpen(false);
              setAttachOpen(false);
            }}
          />
        )}
        <div
          className="flex cursor-grab items-center gap-2 border-b border-border/70 bg-gradient-to-b from-primary/[0.07] to-transparent px-2.5 py-2.5"
          onPointerDown={onHeaderPointerDown}
          onPointerMove={onHeaderPointerMove}
          onPointerUp={onHeaderPointerUp}
        >
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-border/70 bg-card/80 px-2.5 py-1 text-xs font-semibold shadow-sm">
            <Bot className="size-3.5 text-primary" />
            {tx("导演台")}
            {streaming && (
              <span className="size-1.5 animate-pulse rounded-full bg-info" />
            )}
          </span>
          {renaming ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onPointerDown={(e) => e.stopPropagation()}
              onBlur={() => void commitTitle()}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void commitTitle();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  setRenaming(false);
                }
              }}
              className="min-w-0 flex-1 rounded-md border border-primary/40 bg-card px-1.5 py-0.5 text-xs outline-none focus:ring-2 focus:ring-primary/20"
            />
          ) : (
            <button
              type="button"
              title={tx("双击修改会话名称")}
              className="flex min-w-0 flex-1 items-center gap-1 text-left text-xs text-muted-foreground transition-colors hover:text-foreground"
              onClick={() => setSessionOpen((v) => !v)}
              onDoubleClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!session) return;
                setSessionOpen(false);
                setTitleDraft(session.title);
                setRenaming(true);
              }}
            >
              <span className="truncate">{session?.title || tx("新对话")}</span>
              <ChevronDown className="size-3.5 shrink-0" />
            </button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            title={tx("收起到底部")}
            onClick={() => persistOpen(false)}
          >
            <PanelLeftClose className="size-3.5" />
          </Button>
        </div>

        {sessionOpen && (
          <>
            <div className="absolute left-2 right-2 top-12 z-40 max-h-72 overflow-y-auto rounded-xl border border-border bg-card p-1 shadow-lg">
              {sessions.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm",
                    item.id === currentId ? "bg-muted" : "hover:bg-muted",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left"
                    onClick={() => {
                      setCurrentId(item.id);
                      setLive([]);
                      setServerConfirm(null);
                      setClientConfirm(null);
                      setError(null);
                      setSessionOpen(false);
                    }}
                  >
                    {item.title}
                  </button>
                  <button
                    type="button"
                    className="opacity-0 group-hover:opacity-100"
                    aria-label={tx("删除会话")}
                    onClick={() => void deleteSession(item.id)}
                  >
                    <Trash2 className="size-3.5 text-muted-foreground hover:text-danger" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="mt-1 flex w-full items-center gap-1.5 rounded-md border-t border-border px-2 py-1.5 text-sm text-primary hover:bg-muted"
                onClick={() => void createSession()}
              >
                <Plus className="size-3.5" />
                {tx("新建对话")}
              </button>
            </div>
          </>
        )}

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
          {messages.length === 0 && live.length === 0 && !streaming && (
            <div className="flex min-h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <span className="grid size-11 place-items-center rounded-full border border-primary/20 bg-primary/10 text-primary">
                <Sparkles className="size-5" />
              </span>
              <p className="text-sm font-medium">{tx("想让画布做什么？")}</p>
              <p className="max-w-[260px] text-xs leading-relaxed text-muted-foreground">
                {tx("描述你的想法；输入 / 或 @ 引用节点，导演台会直接改画布。")}
              </p>
            </div>
          )}
          <PersistedMessages messages={messages} toolCallIds={toolCallIds} />
          {live.map((item, index) => {
            if (item.kind === "user") {
              return (
                <UserBubble
                  key={`live-${index}`}
                  text={item.text}
                  attachments={item.attachments}
                  refs={item.refs}
                />
              );
            }
            if (item.kind === "assistant") {
              return item.text ? (
                <MarkdownView key={`live-${index}`} source={item.text} />
              ) : streaming ? (
                <p
                  key={`live-${index}`}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                  <Loader2 className="size-3 animate-spin" />
                  {tx("思考中…")}
                </p>
              ) : null;
            }
            if (item.kind === "tool") {
              return (
                <ToolCard
                  key={`live-${index}`}
                  name={item.name}
                  args={item.args}
                  status={item.status}
                  result={item.result}
                />
              );
            }
            return (
              <div
                key={`live-${index}`}
                className="rounded-xl border border-border bg-muted/30 p-2.5"
              >
                <p className="text-sm">{item.question}</p>
                {item.options.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {item.options.map((option) => (
                      <Button
                        key={option}
                        variant="outline"
                        size="sm"
                        onClick={() => void sendMessage(option)}
                      >
                        {option}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {serverConfirm && (
            <ConfirmCard
              title={
                serverConfirm[0]?.title || tx("Agent 想提交生成任务（占用 GPU）")
              }
              calls={serverConfirm}
              onApprove={() => void approveServerConfirm(true)}
              onAuto={() => void approveServerConfirm(true, true)}
              onReject={() => void approveServerConfirm(false)}
            />
          )}
          {clientConfirm && (
            <ConfirmCard
              title={
                clientConfirm[0]?.title ||
                (clientConfirm.some((call) => call.name === "canvas_run_nodes")
                  ? tx("Agent 想提交生成任务（占用 GPU）")
                  : tx("Agent 想删除画布节点"))
              }
              calls={clientConfirm.map((call) => {
                if (call.name !== "canvas_run_nodes") {
                  return { id: call.id, name: call.name, arguments: call.arguments };
                }
                try {
                  const args = JSON.parse(call.arguments || "{}") as {
                    node_ids?: string[];
                    ids?: string[];
                  };
                  const nodes = (args.node_ids ?? args.ids ?? []).join(", ");
                  return {
                    id: call.id,
                    name: call.name,
                    arguments: nodes || tx("当前节点"),
                  };
                } catch {
                  return { id: call.id, name: call.name, arguments: call.arguments };
                }
              })}
              onApprove={() => {
                if (session) void executeAndContinue(session, clientConfirm, false, false);
              }}
              onForce={
                clientConfirm.some((call) => call.name === "canvas_run_nodes")
                  ? () => {
                      if (session) {
                        void executeAndContinue(session, clientConfirm, false, true);
                      }
                    }
                  : undefined
              }
              onAuto={() => {
                if (session) void executeAndContinue(session, clientConfirm, true, false);
              }}
              onReject={() => void rejectClientCalls()}
            />
          )}
          {error && (
            <div className="rounded-lg border border-danger/40 bg-danger/10 px-2.5 py-2 text-xs text-danger">
              {error}
              <button type="button" className="ml-2 underline" onClick={() => setError(null)}>
                {tx("知道了")}
              </button>
            </div>
          )}
        </div>

        <div className="border-t border-border/70 p-2.5">
          {(attachments.length > 0 || refs.length > 0) && (
            <div className="mb-1.5 flex flex-wrap gap-1">
              {attachments.map((item) => (
                <span
                  key={`att-${item.asset_id}`}
                  className="flex items-center gap-1 rounded-full border border-border/70 bg-muted/50 px-2 py-0.5 text-[10px] text-muted-foreground"
                >
                  #{item.asset_id} {item.kind}
                  <button
                    type="button"
                    aria-pressed={item.send_to_model === false}
                    className="rounded-full bg-background/50 px-1.5 py-0.5 text-[10px] text-foreground/80 hover:bg-background"
                    title={
                      item.send_to_model === false
                        ? tx("当前仅用于画布节点，点击改为发给模型")
                        : tx("会发给模型，也可用于画布节点；点击改为仅节点")
                    }
                    onClick={() =>
                      setAttachments((prev) =>
                        prev.map((x) =>
                          x.asset_id === item.asset_id
                            ? { ...x, send_to_model: x.send_to_model === false }
                            : x,
                        ),
                      )
                    }
                  >
                    {item.send_to_model === false ? tx("仅节点") : tx("发给模型")}
                  </button>
                  <button
                    type="button"
                    aria-label={tx("移除附件")}
                    onClick={() =>
                      setAttachments((prev) =>
                        prev.filter((x) => x.asset_id !== item.asset_id),
                      )
                    }
                  >
                    <X className="size-3" />
                  </button>
                </span>
              ))}
              {refs.map((ref) => (
                <span
                  key={`ref-${ref.node_id}`}
                  className="flex items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
                >
                  @{ref.var_name || ref.node_id}
                  <button
                    type="button"
                    aria-label={tx("移除引用")}
                    onClick={() =>
                      setRefs((prev) => prev.filter((x) => x.node_id !== ref.node_id))
                    }
                  >
                    <X className="size-3" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {visionBlocked && (
            <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-warning/30 bg-warning/[0.07] px-2.5 py-1.5 text-[11px] leading-relaxed text-warning">
              <span>
                {tx("当前模型没有视觉能力。请换模型、把附件设为「仅节点」，或去掉图片/视频后再发送。")}
              </span>
              <button type="button" className="underline" onClick={markAllNodeOnly}>
                {tx("全部设为仅节点")}
              </button>
            </div>
          )}
          {refsMediaSkipped && (
            <p className="mb-1.5 text-[10px] leading-relaxed text-muted-foreground">
              {tx("引用的图片/视频不会附带；仍可让导演台按节点信息连线、断线或改属性。")}
            </p>
          )}

          <div className="rounded-[20px] border border-border/80 bg-gradient-to-b from-muted/35 to-card/60 p-2 transition focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15">
            <div className="relative">
            <textarea
              ref={areaRef}
              className="min-h-[84px] w-full resize-none border-0 bg-transparent px-1.5 py-1 text-sm leading-6 outline-none placeholder:text-muted-foreground/80"
              placeholder={tx("描述你的想法；/ 或 @ 引用节点")}
              value={input}
              disabled={streaming}
              onChange={(e) =>
                onInputChange(
                  e.target.value,
                  e.target.selectionStart ?? e.target.value.length,
                )
              }
              onKeyDown={(e) => {
                if (refQuery && filteredRefOptions.length > 0) {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setRefIndex((i) => (i + 1) % filteredRefOptions.length);
                    return;
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setRefIndex(
                      (i) =>
                        (i - 1 + filteredRefOptions.length) % filteredRefOptions.length,
                    );
                    return;
                  }
                  if (e.key === "Enter") {
                    e.preventDefault();
                    pickRef(filteredRefOptions[refIndex]);
                    return;
                  }
                  if (e.key === "Escape") {
                    setRefQuery(null);
                    return;
                  }
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            {refQuery && filteredRefOptions.length > 0 && (
              <div className="absolute bottom-full left-0 z-40 mb-1 max-h-56 w-full overflow-y-auto rounded-xl border border-border bg-card p-1 shadow-lg">
                <div className="px-2 py-1 text-[10px] text-muted-foreground">
                  {tx("引用画布节点")}
                </div>
                {filteredRefOptions.map((option, index) => (
                  <button
                    key={option.nodeId}
                    type="button"
                    className={cn(
                      "flex w-full flex-col rounded-md px-2 py-1 text-left",
                      index === refIndex ? "bg-muted" : "hover:bg-muted",
                    )}
                    onMouseEnter={() => setRefIndex(index)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pickRef(option);
                    }}
                  >
                    <span className="flex items-center gap-1 text-xs">
                      <span className="font-medium text-primary">@{option.handle}</span>
                      <span className="text-muted-foreground">· {option.title}</span>
                      {option.status === "config" && (
                        <span className="rounded bg-muted px-1 text-[9px] text-muted-foreground">
                          {tx("仅配置")}
                        </span>
                      )}
                    </span>
                    <span className="truncate text-[10px] text-muted-foreground">
                      {option.preview}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

            <div className="mt-1 flex items-center gap-0.5">
              <input
                ref={fileRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) =>
                  void uploadAttachments(e.target.files, pendingFileKind)
                }
              />
              <div className="relative">
                <ComposerButton
                  icon={<Plus className="size-3.5" />}
                  label={tx("添加")}
                  active={attachOpen}
                  compact
                  onClick={() => {
                    setAttachOpen((value) => !value);
                    setSkillOpen(false);
                    setModelOpen(false);
                  }}
                />
                {attachOpen && (
                  <>
                    <div className="absolute bottom-full left-0 z-40 mb-2 w-64 rounded-2xl border border-border bg-card/95 p-1.5 shadow-2xl backdrop-blur-xl">
                      {[
                        {
                          kind: "image",
                          icon: ImageIcon,
                          label: tx("图片"),
                          desc: "jpg, jpeg, png, webp",
                        },
                        {
                          kind: "video",
                          icon: Video,
                          label: tx("视频"),
                          desc: "mp4, mov, webm",
                        },
                        {
                          kind: "text",
                          icon: FileText,
                          label: tx("剧本 / 文本"),
                          desc: "txt, md, json, srt",
                        },
                        {
                          kind: "audio",
                          icon: AudioLines,
                          label: tx("音频"),
                          desc: "mp3, wav, m4a",
                        },
                      ].map((item) => (
                        <button
                          key={item.kind}
                          type="button"
                          className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted/70"
                          onClick={() => {
                            const input = fileRef.current;
                            if (input) {
                              input.accept =
                                item.kind === "image"
                                  ? "image/*"
                                  : item.kind === "video"
                                    ? "video/*"
                                    : item.kind === "audio"
                                      ? "audio/*"
                                      : ".txt,.md,.json,.srt,.vtt";
                              setPendingFileKind(item.kind);
                              input.click();
                            }
                            setAttachOpen(false);
                          }}
                        >
                          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-foreground/80">
                            <item.icon className="size-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-medium">
                              {item.label}
                            </span>
                            <span className="block truncate text-[10px] text-muted-foreground">
                              {item.desc}
                            </span>
                          </span>
                        </button>
                      ))}
                      <div className="mt-1 border-t border-border/70 pt-1">
                        <button
                          type="button"
                          className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted/70"
                          onClick={() => {
                            setAttachOpen(false);
                            setAssetOpen(true);
                          }}
                        >
                          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-foreground/80">
                            <FolderOpen className="size-4" />
                          </span>
                          <span className="text-xs font-medium">
                            {tx("从资源库选择")}
                          </span>
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="mx-0.5 h-5 w-px bg-border/80" aria-hidden />
              <div className="relative">
                <ComposerButton
                  icon={<Sparkles className="size-3.5" />}
                  label={tx("技能")}
                  value={activeSkill?.name}
                  active={skillOpen}
                  compact
                  onClick={() => {
                    setSkillOpen((value) => !value);
                    setModelOpen(false);
                    setAttachOpen(false);
                  }}
                />
                {skillOpen && (
                  <>
                    <div className="absolute bottom-full left-0 z-40 mb-2 w-72 rounded-2xl border border-border bg-card/95 p-1.5 shadow-2xl backdrop-blur-xl">
                      <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        {tx("技能")}
                      </div>
                      {skills.map((skill) => (
                        <button
                          key={skill.name}
                          type="button"
                          className={cn(
                            "flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted/70",
                            activeSkill?.name === skill.name && "bg-primary/[0.07]",
                          )}
                          onClick={() => void chooseSkill(skill.name)}
                        >
                          <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                            <Sparkles className="size-3.5" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-1 text-xs font-medium">
                              {skill.name}
                              {activeSkill?.name === skill.name && (
                                <Check className="size-3 text-primary" />
                              )}
                            </span>
                            <span className="line-clamp-2 text-[10px] leading-relaxed text-muted-foreground">
                              {skill.description}
                            </span>
                          </span>
                        </button>
                      ))}
                      <div className="mt-1 flex gap-1 border-t border-border/70 pt-1">
                        <button
                          type="button"
                          className="flex flex-1 items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] hover:bg-muted"
                          onClick={() => {
                            setSkillOpen(false);
                            uploadRef.current?.click();
                          }}
                        >
                          <Upload className="size-3" />
                          {tx("上传技能")}
                        </button>
                        <button
                          type="button"
                          className="flex flex-1 items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] hover:bg-muted"
                          onClick={() => {
                            setSkillOpen(false);
                            setSkillManageOpen(true);
                          }}
                        >
                          <Settings2 className="size-3" />
                          {tx("管理")}
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="relative">
                <ComposerButton
                  icon={<Cpu className="size-3.5" />}
                  label={tx("模型")}
                  value={selectedModel?.model || tx("默认")}
                  active={modelOpen}
                  compact
                  onClick={() => {
                    setModelOpen((value) => !value);
                    setSkillOpen(false);
                    setAttachOpen(false);
                  }}
                />
                {modelOpen && (
                  <div className="absolute bottom-full left-1/2 z-40 mb-2 w-72 -translate-x-1/2 rounded-2xl border border-border bg-card/95 p-1.5 shadow-2xl backdrop-blur-xl">
                        <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          {tx("模型")}
                        </div>
                        <button
                          type="button"
                          className={cn(
                            "flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted/70",
                            modelChoice === FOLLOW_DEFAULT && "bg-primary/[0.07]",
                          )}
                          onClick={() => void changeModel(FOLLOW_DEFAULT)}
                        >
                          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                            <Cpu className="size-3.5" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-1 text-xs font-medium">
                              {tx("跟随系统默认")}
                              {modelChoice === FOLLOW_DEFAULT && (
                                <Check className="size-3 text-primary" />
                              )}
                            </span>
                            <span className="block truncate text-[10px] text-muted-foreground">
                              {systemDefault?.label || tx("使用系统设置里的默认 LLM")}
                            </span>
                          </span>
                        </button>
                        <div className="my-1 border-t border-border/70" />
                        <div className="max-h-64 overflow-y-auto">
                          {llmOptions.map((item) => (
                            <button
                              key={item.value}
                              type="button"
                              className={cn(
                                "flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted/70",
                                modelChoice === item.value && "bg-primary/[0.07]",
                              )}
                              onClick={() => void changeModel(item.value)}
                            >
                              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-muted text-foreground/70">
                                <Cpu className="size-3.5" />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="flex items-center gap-1 text-xs font-medium">
                                  <span className="truncate">{item.model}</span>
                                  {modelChoice === item.value && (
                                    <Check className="size-3 text-primary" />
                                  )}
                                </span>
                                <span className="mt-0.5 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
                                  <span className="truncate">{item.provider}</span>
                                  {item.vision && (
                                    <span className="rounded-full bg-muted px-1.5 py-0.5">
                                      {tx("视觉")}
                                    </span>
                                  )}
                                  {item.tools && (
                                    <span className="rounded-full bg-muted px-1.5 py-0.5">
                                      {tx("工具")}
                                    </span>
                                  )}
                                </span>
                              </span>
                            </button>
                          ))}
                          {llmOptions.length === 0 && (
                            <p className="px-2.5 py-2 text-[11px] text-muted-foreground">
                              {tx("尚未启用 LLM 模型。请先在服务提供方里勾选。")}
                            </p>
                          )}
                        </div>
                  </div>
                )}
              </div>
              {!currentVision && (
                <span
                  className="ml-0.5 grid size-7 place-items-center rounded-full border border-warning/30 bg-warning/[0.07] text-warning"
                  title={tx("无视觉")}
                >
                  <EyeOff className="size-3.5" />
                </span>
              )}
              <span className="flex-1" />
              {streaming ? (
                <button
                  type="button"
                  className="grid size-9 place-items-center rounded-full border border-border bg-card text-muted-foreground transition hover:text-foreground"
                  onClick={stopStreaming}
                  aria-label={tx("停止")}
                >
                  <X className="size-4" />
                </button>
              ) : (
                <button
                  type="button"
                  className="grid size-9 place-items-center rounded-full bg-primary text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-35"
                  disabled={
                    (!input.trim() && attachments.length === 0 && refs.length === 0) ||
                    visionBlocked ||
                    Boolean(serverConfirm || clientConfirm)
                  }
                  onClick={send}
                  aria-label={tx("发送")}
                >
                  <Send className="size-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <input
        ref={uploadRef}
        type="file"
        accept=".md,.zip"
        className="hidden"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            await api.uploadAgentSkill(file);
            await skillsQuery.refetch();
          } catch (err) {
            setError(err instanceof Error ? err.message : "上传技能失败");
          }
          if (uploadRef.current) uploadRef.current.value = "";
        }}
      />

      {assetOpen && (
        <LightboxShell
          onClose={() => setAssetOpen(false)}
          ariaLabel={tx("选择资源")}
          className="max-w-2xl"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-medium">{tx("从资源库选择")}</h3>
            <div className="flex items-center gap-1">
              <select
                className="rounded-md border border-border bg-card px-2 py-1 text-xs"
                value={assetKind}
                onChange={(e) => setAssetKind(e.target.value)}
              >
                <option value="image">{tx("图片")}</option>
                <option value="video">{tx("视频")}</option>
                <option value="audio">{tx("音频")}</option>
                <option value="text">{tx("文本")}</option>
              </select>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={() => setAssetOpen(false)}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>
          <AssetPickerList kind={assetKind} onPick={addAssetAttachment} />
        </LightboxShell>
      )}

      {skillManageOpen && (
        <LightboxShell
          onClose={() => setSkillManageOpen(false)}
          ariaLabel={tx("管理技能")}
          className="max-w-xl"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-medium">{tx("管理技能")}</h3>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => setSkillManageOpen(false)}
            >
              <X className="size-4" />
            </Button>
          </div>
          <div className="space-y-2 overflow-y-auto p-3">
            {(skillsQuery.data ?? []).map((skill) => (
              <SkillRow
                key={skill.name}
                skill={skill}
                onView={async () => {
                  try {
                    const detail = await api.getAgentSkill(skill.name);
                    setSkillView({
                      name: detail.name,
                      body: detail.body,
                      license: detail.license,
                      compatibility: detail.compatibility,
                      allowed_tools: detail.allowed_tools,
                      files: detail.files,
                    });
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "读取技能失败");
                  }
                }}
                onToggle={async () => {
                  await api.setAgentSkillEnabled(skill.name, !skill.enabled);
                  await skillsQuery.refetch();
                }}
                onDelete={
                  skill.builtin
                    ? undefined
                    : async () => {
                        await api.deleteAgentSkill(skill.name);
                        await skillsQuery.refetch();
                      }
                }
              />
            ))}
          </div>
        </LightboxShell>
      )}

      {skillView && (
        <LightboxShell
          onClose={() => setSkillView(null)}
          ariaLabel={tx("技能详情")}
          className="max-w-2xl"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-medium">{skillView.name}</h3>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => setSkillView(null)}
            >
              <X className="size-4" />
            </Button>
          </div>
          <div className="max-h-[70vh] overflow-y-auto p-4">
            {(skillView.license || skillView.compatibility) && (
              <div className="mb-3 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                {skillView.license && (
                  <span className="rounded bg-muted px-1.5 py-0.5">
                    {skillView.license}
                  </span>
                )}
                {skillView.compatibility && (
                  <span className="rounded bg-muted px-1.5 py-0.5">
                    {skillView.compatibility}
                  </span>
                )}
              </div>
            )}
            {!!skillView.files?.length && (
              <div className="mb-3 flex flex-wrap gap-1">
                {skillView.files.map((file) => (
                  <span
                    key={file.path}
                    className="rounded border border-border bg-muted/50 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                  >
                    {file.path}
                    {file.is_text ? "" : ` · ${Math.ceil(file.size / 1024)}KB`}
                  </span>
                ))}
              </div>
            )}
            <MarkdownView source={skillView.body} />
          </div>
        </LightboxShell>
      )}
    </>
  );
}

function ComposerButton({
  icon,
  label,
  value,
  active,
  compact,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  value?: string;
  active?: boolean;
  compact?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={label}
      className={cn(
        "flex h-8 min-w-0 items-center gap-1 rounded-full px-2 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
        active && "bg-primary/10 text-primary hover:bg-primary/10 hover:text-primary",
      )}
      onClick={onClick}
    >
      {icon}
      {!compact && <span className="font-medium">{label}</span>}
      {value && <span className="max-w-[96px] truncate opacity-80">{value}</span>}
      <ChevronDown className="size-3 shrink-0 opacity-50" />
    </button>
  );
}

function ConfirmCard({
  title,
  calls,
  onApprove,
  onForce,
  onAuto,
  onReject,
}: {
  title: string;
  calls: { id: string; name: string; arguments: string }[];
  onApprove: () => void;
  onForce?: () => void;
  onAuto: () => void;
  onReject: () => void;
}) {
  const tx = useTx();
  return (
    <div className="rounded-2xl border border-warning/30 bg-warning/[0.06] p-3">
      <p className="text-xs font-medium">{title}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">
        {calls.map((call) => (
          <li key={call.id}>
            <span className="font-medium text-foreground">{call.name}</span>{" "}
            {call.arguments.slice(0, 120)}
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Button size="sm" onClick={onApprove}>
          <Check className="size-3.5" />
          {tx(onForce ? "执行当前节点" : "确认执行")}
        </Button>
        {onForce && (
          <Button variant="outline" size="sm" onClick={onForce}>
            <Zap className="size-3.5" />
            {tx("强制执行含上游")}
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onAuto}>
          <ShieldCheck className="size-3.5" />
          {tx("本会话自动允许")}
        </Button>
        <Button variant="outline" size="sm" onClick={onReject}>
          <Ban className="size-3.5" />
          {tx("取消")}
        </Button>
      </div>
    </div>
  );
}

function SkillRow({
  skill,
  onView,
  onToggle,
  onDelete,
}: {
  skill: AgentSkillOut;
  onView: () => void;
  onToggle: () => void;
  onDelete?: () => void;
}) {
  const tx = useTx();
  return (
    <div className="flex items-start gap-2 rounded-lg border border-border px-2.5 py-2">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          {skill.name}
          <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">
            {skill.source === "builtin" ? tx("内置") : tx("用户")}
          </span>
        </p>
        <p className="text-[11px] text-muted-foreground">{skill.description}</p>
        <p className="mt-1 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span>{skill.file_count ?? 1} {tx("个文件")}</span>
          {skill.has_scripts && <span className="text-warning">{tx("含脚本")}</span>}
          {skill.license && <span>{skill.license}</span>}
        </p>
      </div>
      <Button variant="ghost" size="sm" onClick={onView}>
        {tx("查看")}
      </Button>
      <Button variant="outline" size="sm" onClick={onToggle}>
        {skill.enabled ? tx("停用") : tx("启用")}
      </Button>
      {onDelete && (
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onDelete}
          aria-label={tx("删除")}
        >
          <Trash2 className="size-3.5 text-danger" />
        </Button>
      )}
    </div>
  );
}

function AssetPickerList({
  kind,
  onPick,
}: {
  kind: string;
  onPick: (asset: AssetOut) => void;
}) {
  const tx = useTx();
  const { data, isLoading } = useQuery({
    queryKey: ["agent-assets", kind],
    queryFn: () => api.listAssets(kind, true),
  });
  return (
    <div className="grid max-h-[60vh] grid-cols-3 gap-2 overflow-y-auto p-3 sm:grid-cols-4">
      {isLoading && (
        <p className="col-span-full text-sm text-muted-foreground">{tx("加载中…")}</p>
      )}
      {!isLoading && !data?.length && (
        <p className="col-span-full text-sm text-muted-foreground">
          {tx("资源库暂无该类型文件")}
        </p>
      )}
      {(data ?? []).map((asset) => (
        <button
          key={asset.id}
          type="button"
          className="overflow-hidden rounded-lg border border-border text-left transition hover:border-primary"
          onClick={() => onPick(asset)}
        >
          <MediaThumb
            assetId={asset.id}
            kind={asset.kind}
            className="aspect-video w-full object-cover"
          />
          <span className="block truncate px-1.5 py-1 text-[10px] text-muted-foreground">
            #{asset.id} {asset.path}
          </span>
        </button>
      ))}
    </div>
  );
}

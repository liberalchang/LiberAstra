import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Loader2, Plus, RefreshCw, Search, Send, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  api,
  type NotificationChannelOut,
  type NotificationChannelType,
  type NotificationDeliveryOut,
  type NotificationEvent,
  type NotificationRuleOut,
  type TelegramChatCandidate,
} from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

type Tab = "channels" | "rules" | "deliveries";

interface ChannelDraft {
  name: string;
  type: NotificationChannelType;
  maxAttempts: string;
  backoffSeconds: string;
  timeoutSeconds: string;
  config: Record<string, string>;
  clearSecret: boolean;
}

interface RuleDraft {
  id: number | null;
  name: string;
  enabled: boolean;
  events: NotificationEvent[];
  interval: string;
  jobKinds: string;
  maxJobs: string;
  quietEnabled: boolean;
  quietStart: string;
  quietEnd: string;
  quietTimezone: string;
  includeOutputs: boolean;
  templateSucceeded: string;
  templateFailed: string;
  templateProgress: string;
  channelIds: number[];
}

const CHANNEL_TYPES: { value: NotificationChannelType; label: string }[] = [
  { value: "telegram", label: "Telegram" },
  { value: "feishu", label: "飞书" },
  { value: "dingtalk", label: "钉钉" },
  { value: "bark", label: "Bark" },
  { value: "webhook", label: "Webhook" },
];

const CHANNEL_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  CHANNEL_TYPES.map((item) => [item.value, item.label]),
);

const TELEGRAM_CHAT_TYPE_LABEL: Record<string, string> = {
  private: "私聊",
  group: "群组",
  supergroup: "超级群",
  channel: "频道",
};

const EVENT_OPTIONS: { value: NotificationEvent; label: string }[] = [
  { value: "job.succeeded", label: "成功" },
  { value: "job.failed", label: "失败" },
  { value: "job.canceled", label: "取消" },
  { value: "job.progress", label: "运行进度" },
];

const EMPTY_CHANNEL: ChannelDraft = {
  name: "",
  type: "telegram",
  maxAttempts: "3",
  backoffSeconds: "30",
  timeoutSeconds: "10",
  config: {},
  clearSecret: false,
};

const EMPTY_RULE: RuleDraft = {
  id: null,
  name: "",
  enabled: true,
  events: ["job.succeeded", "job.failed"],
  interval: "900",
  jobKinds: "",
  maxJobs: "10",
  quietEnabled: false,
  quietStart: "22:00",
  quietEnd: "08:00",
  quietTimezone: "Asia/Shanghai",
  includeOutputs: true,
  templateSucceeded: "",
  templateFailed: "",
  templateProgress: "",
  channelIds: [],
};

function isMasked(value: string) {
  return value.includes("***") || value.includes("****");
}

function channelConfigValue(channel: NotificationChannelOut, key: string): string {
  const value = channel.config[key];
  if (typeof value === "string") return isMasked(value) ? "" : value;
  if (typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") {
    const text = JSON.stringify(value);
    return text.includes("****") ? "" : text;
  }
  return "";
}

function channelMaskedPlaceholder(
  channel: NotificationChannelOut | null,
  key: string,
): string | undefined {
  if (!channel) return undefined;
  const value = channel.config[key];
  if (typeof value === "string" && isMasked(value)) return value;
  if (key === "headers" && value && typeof value === "object") {
    const text = JSON.stringify(value);
    return text.includes("****") ? text : undefined;
  }
  return undefined;
}

function draftFromChannel(channel: NotificationChannelOut): ChannelDraft {
  const config: Record<string, string> = {};
  for (const key of Object.keys(channel.config)) {
    config[key] = channelConfigValue(channel, key);
  }
  return {
    name: channel.name,
    type: channel.type,
    maxAttempts: String(channel.max_attempts),
    backoffSeconds: String(channel.backoff_seconds),
    timeoutSeconds: String(channel.timeout_seconds),
    config,
    clearSecret: false,
  };
}

function buildChannelConfig(draft: ChannelDraft, tx: (zh: string) => string): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  const put = (key: string) => {
    const value = (draft.config[key] ?? "").trim();
    if (value) config[key] = value;
  };
  config.use_proxy = draft.config.use_proxy !== "false";
  if (draft.type === "telegram") {
    put("bot_token");
    put("chat_id");
    config.parse_mode = draft.config.parse_mode || "HTML";
    config.disable_preview = draft.config.disable_preview !== "false";
  } else if (draft.type === "feishu") {
    put("webhook_url");
    put("secret");
  } else if (draft.type === "dingtalk") {
    put("webhook_url");
    put("secret");
    config.at_mobiles = (draft.config.at_mobiles ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    config.at_all = draft.config.at_all === "true";
  } else if (draft.type === "bark") {
    put("server_url");
    put("device_key");
    put("group");
    put("sound");
  } else {
    put("url");
    put("hmac_secret");
    put("body_template");
    const headers = (draft.config.headers ?? "").trim();
    if (headers) {
      try {
        const parsed = JSON.parse(headers) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("headers");
        }
        config.headers = parsed;
      } catch {
        throw new Error(tx("headers 必须是 JSON 对象"));
      }
    }
  }
  return config;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function statusClass(value: string): string {
  if (value === "sent") return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  if (value === "failed") return "bg-destructive/10 text-destructive";
  if (value === "pending" || value === "sending") {
    return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  return "bg-muted text-muted-foreground";
}

function CheckRow({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-foreground">
      <input
        type="checkbox"
        className="size-4 rounded border-border accent-primary"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

export function NotificationsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("channels");
  const [notice, setNotice] = useState<string | null>(null);
  const [channelDraft, setChannelDraft] = useState<ChannelDraft | null>(null);
  const [editingChannelId, setEditingChannelId] = useState<number | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft | null>(null);
  const [deliveryStatus, setDeliveryStatus] = useState("");
  const [language, setLanguage] = useState("zh-CN");
  const [proxy, setProxy] = useState("");
  const [publicUrl, setPublicUrl] = useState("");
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [savingChannel, setSavingChannel] = useState(false);
  const [savingRule, setSavingRule] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [channelError, setChannelError] = useState<string | null>(null);
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [chatCandidates, setChatCandidates] = useState<TelegramChatCandidate[]>([]);
  const [chatLookupBusy, setChatLookupBusy] = useState(false);
  const [chatLookupError, setChatLookupError] = useState<string | null>(null);
  const channelErrorRef = useRef<HTMLParagraphElement | null>(null);
  const ruleErrorRef = useRef<HTMLParagraphElement | null>(null);

  const channels = useQuery({
    queryKey: ["notification-channels"],
    queryFn: api.listNotificationChannels,
  });
  const rules = useQuery({
    queryKey: ["notification-rules"],
    queryFn: api.listNotificationRules,
  });
  const deliveries = useQuery({
    queryKey: ["notification-deliveries", deliveryStatus],
    queryFn: () =>
      api.listNotificationDeliveries({ status: deliveryStatus || undefined, limit: 100 }),
    refetchInterval: 5000,
  });
  const prefs = useQuery({
    queryKey: ["system-preferences"],
    queryFn: api.getPreferences,
  });

  useEffect(() => {
    if (!prefs.data) return;
    setLanguage(prefs.data.notification_language || "zh-CN");
    setProxy(prefs.data.notification_proxy || "");
    setPublicUrl(prefs.data.notification_public_base_url || "");
  }, [prefs.data]);

  const channelName = useMemo(() => {
    const map = new Map((channels.data ?? []).map((channel) => [channel.id, channel.name]));
    return (id: number | null) => (id == null ? "—" : (map.get(id) ?? `#${id}`));
  }, [channels.data]);

  const groupedChannels = useMemo(() => {
    const groups: Record<string, NotificationChannelOut[]> = {};
    for (const channel of channels.data ?? []) {
      (groups[channel.type] ??= []).push(channel);
    }
    return groups;
  }, [channels.data]);

  const editingChannel = useMemo(
    () => (channels.data ?? []).find((channel) => channel.id === editingChannelId) ?? null,
    [channels.data, editingChannelId],
  );

  const showChannelError = (message: string) => {
    setChannelError(message);
    requestAnimationFrame(() => {
      channelErrorRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  };

  const showRuleError = (message: string) => {
    setRuleError(message);
    requestAnimationFrame(() => {
      ruleErrorRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  };

  const resetChatLookup = () => {
    setChatCandidates([]);
    setChatLookupError(null);
  };

  const toggleChannel = async (channel: NotificationChannelOut) => {
    setTogglingId(channel.id);
    setNotice(null);
    try {
      await api.updateNotificationChannel(channel.id, { enabled: !channel.enabled });
      await refresh();
      setNotice(channel.enabled ? tx("渠道已停用") : tx("渠道已启用"));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setTogglingId(null);
    }
  };

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notification-channels"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-deliveries"] }),
    ]);
  };

  const saveGeneral = async () => {
    setSavingGeneral(true);
    setNotice(null);
    try {
      await api.updatePreferences({
        notification_language: language,
        notification_proxy: proxy.trim(),
        notification_public_base_url: publicUrl.trim(),
      });
      await queryClient.invalidateQueries({ queryKey: ["system-preferences"] });
      setNotice(tx("通知通用设置已保存"));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingGeneral(false);
    }
  };

  const openNewChannel = () => {
    setEditingChannelId(null);
    setChannelDraft({ ...EMPTY_CHANNEL, config: {} });
    setChannelError(null);
    resetChatLookup();
    setNotice(null);
  };

  const openEditChannel = (channel: NotificationChannelOut) => {
    setEditingChannelId(channel.id);
    setChannelDraft(draftFromChannel(channel));
    setChannelError(null);
    resetChatLookup();
    setNotice(null);
  };

  const saveChannel = async () => {
    if (!channelDraft) return;
    setSavingChannel(true);
    setNotice(null);
    setChannelError(null);
    try {
      const config = buildChannelConfig(channelDraft, tx);
      const body: Record<string, unknown> = {
        name: channelDraft.name.trim(),
        config,
        max_attempts: Number(channelDraft.maxAttempts),
        backoff_seconds: Number(channelDraft.backoffSeconds),
        timeout_seconds: Number(channelDraft.timeoutSeconds),
      };
      if (editingChannelId == null) {
        body.type = channelDraft.type;
        await api.createNotificationChannel(body);
      } else {
        body.clear_secret = channelDraft.clearSecret;
        await api.updateNotificationChannel(editingChannelId, body);
      }
      await refresh();
      setChannelDraft(null);
      setEditingChannelId(null);
      resetChatLookup();
      setNotice(tx("渠道已保存"));
    } catch (error) {
      showChannelError(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingChannel(false);
    }
  };

  const testChannel = async (channel: NotificationChannelOut) => {
    setTestingId(channel.id);
    setNotice(null);
    try {
      const result = await api.testNotificationChannel(channel.id);
      setNotice(result.ok ? tx("测试消息已发送") : result.message);
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setTestingId(null);
    }
  };

  const deleteChannel = async (channel: NotificationChannelOut) => {
    if (!window.confirm(tx("删除渠道「{name}」？已排队的通知会被跳过。", { name: channel.name }))) {
      return;
    }
    try {
      await api.deleteNotificationChannel(channel.id);
      await refresh();
      setNotice(tx("渠道已删除"));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const openNewRule = () => {
    setRuleDraft({
      ...EMPTY_RULE,
      channelIds: channels.data?.[0] ? [channels.data[0].id] : [],
    });
    setRuleError(null);
    setNotice(null);
  };

  const openEditRule = (rule: NotificationRuleOut) => {
    setRuleDraft({
      id: rule.id,
      name: rule.name,
      enabled: rule.enabled,
      events: rule.events,
      interval: String(rule.progress_interval_seconds),
      jobKinds: rule.job_kinds.join(", "),
      maxJobs: String(rule.max_jobs_per_digest),
      quietEnabled: Boolean(rule.quiet_hours),
      quietStart: rule.quiet_hours?.start ?? "22:00",
      quietEnd: rule.quiet_hours?.end ?? "08:00",
      quietTimezone: rule.quiet_hours?.timezone ?? "Asia/Shanghai",
      includeOutputs: rule.include_outputs,
      templateSucceeded: rule.template_succeeded ?? "",
      templateFailed: rule.template_failed ?? "",
      templateProgress: rule.template_progress ?? "",
      channelIds: rule.channel_ids,
    });
    setRuleError(null);
    setNotice(null);
  };

  const saveRule = async () => {
    if (!ruleDraft) return;
    if (ruleDraft.events.length === 0) {
      showRuleError(tx("至少选择一个事件"));
      return;
    }
    if (ruleDraft.channelIds.length === 0) {
      showRuleError(tx("至少选择一个渠道"));
      return;
    }
    setSavingRule(true);
    setNotice(null);
    setRuleError(null);
    try {
      const body: Record<string, unknown> = {
        name: ruleDraft.name.trim(),
        enabled: ruleDraft.enabled,
        events: ruleDraft.events,
        progress_interval_seconds: Number(ruleDraft.interval),
        job_kinds: ruleDraft.jobKinds
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        max_jobs_per_digest: Number(ruleDraft.maxJobs),
        quiet_hours: ruleDraft.quietEnabled
          ? {
              start: ruleDraft.quietStart,
              end: ruleDraft.quietEnd,
              timezone: ruleDraft.quietTimezone,
            }
          : null,
        include_outputs: ruleDraft.includeOutputs,
        template_succeeded: ruleDraft.templateSucceeded || null,
        template_failed: ruleDraft.templateFailed || null,
        template_progress: ruleDraft.templateProgress || null,
        channel_ids: ruleDraft.channelIds,
      };
      if (ruleDraft.id == null) {
        await api.createNotificationRule(body);
      } else {
        await api.updateNotificationRule(ruleDraft.id, body);
      }
      await refresh();
      setRuleDraft(null);
      setNotice(tx("规则已保存"));
    } catch (error) {
      showRuleError(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingRule(false);
    }
  };

  const deleteRule = async (rule: NotificationRuleOut) => {
    if (!window.confirm(tx("删除规则「{name}」？", { name: rule.name }))) return;
    try {
      await api.deleteNotificationRule(rule.id);
      await refresh();
      setNotice(tx("规则已删除"));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const retryDelivery = async (delivery: NotificationDeliveryOut) => {
    try {
      await api.retryNotificationDelivery(delivery.id);
      await refresh();
      setNotice(tx("已加入重试队列"));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const setConfig = (key: string, value: string) =>
    setChannelDraft((draft) =>
      draft ? { ...draft, config: { ...draft.config, [key]: value } } : draft,
    );

  const lookupTelegramChats = async () => {
    if (!channelDraft) return;
    const typedToken = (channelDraft.config.bot_token ?? "").trim();
    if (!typedToken && editingChannelId == null) {
      setChatCandidates([]);
      setChatLookupError(tx("请先填写 Bot Token"));
      return;
    }
    setChatLookupBusy(true);
    setChatLookupError(null);
    setChatCandidates([]);
    setNotice(null);
    try {
      const result = await api.listTelegramChats({
        channel_id: editingChannelId ?? undefined,
        bot_token: typedToken || undefined,
        use_proxy: channelDraft.config.use_proxy !== "false",
      });
      if (result.items.length === 0) {
        setChatLookupError(
          tx("没有找到最近会话。请先给 bot 发送 /start，或把 bot 拉进群后再试。"),
        );
        return;
      }
      if (result.items.length === 1) {
        const chat = result.items[0];
        setConfig("chat_id", chat.id);
        setNotice(tx("已填入 Chat ID：{id}", { id: chat.id }));
        return;
      }
      setChatCandidates(result.items);
    } catch (error) {
      setChatLookupError(error instanceof Error ? error.message : String(error));
    } finally {
      setChatLookupBusy(false);
    }
  };

  const applyChatCandidate = (chat: TelegramChatCandidate) => {
    setConfig("chat_id", chat.id);
    resetChatLookup();
    setNotice(tx("已填入 Chat ID：{id}", { id: chat.id }));
  };

  return (
    <div className="space-y-5">
      <PageHeader
        kind="settings"
        icon={Bell}
        title={tx("通知")}
        description={tx("任务完成、失败和运行进度推送到 Telegram、飞书、钉钉、Bark 或 Webhook。")}
      />

      {notice ? (
        <div role="status" className="rounded-xl border border-border bg-muted px-4 py-3 text-sm text-foreground">
          {notice}
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{tx("通用")}</CardTitle>
          <CardDescription>{tx("推送语言和全局出站代理。空代理表示沿用环境变量。")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <Field label={tx("推送语言")} hint={tx("不跟随界面语言；所有渠道共用。")}>
            <select className={selectClass} value={language} onChange={(event) => setLanguage(event.target.value)}>
              <option value="zh-CN">中文</option>
              <option value="en">English</option>
            </select>
          </Field>
          <Field label={tx("出站代理")} hint={tx("例如 http://127.0.0.1:7890；不支持用户名密码。")}>
            <Input value={proxy} onChange={(event) => setProxy(event.target.value)} placeholder="http://127.0.0.1:7890" />
          </Field>
          <Field label={tx("公开访问地址")} hint={tx("用于消息里的任务链接；留空则不带链接。")}>
            <Input value={publicUrl} onChange={(event) => setPublicUrl(event.target.value)} placeholder="http://10.0.0.2:8000" />
          </Field>
          <div className="md:col-span-3">
            <Button onClick={saveGeneral} disabled={savingGeneral}>
              {savingGeneral ? tx("保存中…") : tx("保存通用设置")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          options={[
            { value: "channels", label: tx("渠道") },
            { value: "rules", label: tx("规则") },
            { value: "deliveries", label: tx("投递记录") },
          ]}
          value={tab}
          onChange={setTab}
          ariaLabel={tx("通知设置页签")}
        />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw /> {tx("刷新")}
          </Button>
          {tab === "channels" ? (
            <Button size="sm" onClick={openNewChannel}>
              <Plus /> {tx("新建渠道")}
            </Button>
          ) : null}
          {tab === "rules" ? (
            <Button size="sm" onClick={openNewRule}>
              <Plus /> {tx("新建规则")}
            </Button>
          ) : null}
        </div>
      </div>

      {tab === "channels" ? (
        <div className="space-y-4">
          {channelDraft ? (
            <Card>
              <CardHeader>
                <CardTitle>{editingChannelId == null ? tx("新建渠道") : tx("编辑渠道")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label={tx("名称")}>
                    <Input
                      value={channelDraft.name}
                      onChange={(event) =>
                        setChannelDraft((draft) => (draft ? { ...draft, name: event.target.value } : draft))
                      }
                    />
                  </Field>
                  <Field label={tx("类型")}>
                    <select
                      className={selectClass}
                      value={channelDraft.type}
                      disabled={editingChannelId != null}
                      onChange={(event) => {
                        setChannelDraft((draft) =>
                          draft
                            ? { ...draft, type: event.target.value as NotificationChannelType, config: {} }
                            : draft,
                        );
                        resetChatLookup();
                      }}
                    >
                      {CHANNEL_TYPES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>

                {editingChannelId != null ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {tx("密钥和含 token 的地址已保存，只显示掩码；留空保存会保留原值。Bark 服务器地址不是密钥，会完整回填。")}
                  </p>
                ) : null}

                {channelDraft.type === "telegram" ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Bot Token">
                      <Input
                        type="password"
                        value={channelDraft.config.bot_token ?? ""}
                        onChange={(event) => {
                          setConfig("bot_token", event.target.value);
                          resetChatLookup();
                        }}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "bot_token") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <div className="space-y-1.5">
                      <Field
                        label="Chat ID"
                        hint={tx("聊天 ID，不是 bot ID。点右侧搜索图标可从 bot 最近消息中获取；也可以私聊发 /start 后用 @userinfobot 查数字 ID，群/频道是负数。")}
                        trailing={
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-foreground"
                            aria-label={tx("自动获取会话 ID")}
                            title={tx("自动获取 Chat ID")}
                            aria-busy={chatLookupBusy}
                            disabled={chatLookupBusy}
                            onClick={lookupTelegramChats}
                          >
                            {chatLookupBusy ? <Loader2 className="animate-spin" /> : <Search />}
                          </Button>
                        }
                      >
                        <Input
                          className="pr-12"
                          value={channelDraft.config.chat_id ?? ""}
                          onChange={(event) => {
                            setConfig("chat_id", event.target.value);
                            resetChatLookup();
                          }}
                        />
                      </Field>
                      {chatLookupError ? (
                        <p role="alert" className="text-xs leading-relaxed text-destructive">
                          {chatLookupError}
                        </p>
                      ) : null}
                      {chatCandidates.length > 1 ? (
                        <div className="rounded-xl border border-border bg-field p-2">
                          <p className="px-1 pb-1 text-xs font-medium text-foreground">
                            {tx("选择要填入的会话")}
                          </p>
                          <div className="space-y-0.5">
                            {chatCandidates.map((chat) => (
                              <button
                                key={chat.id}
                                type="button"
                                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                onClick={() => applyChatCandidate(chat)}
                              >
                                <span className="min-w-0">
                                  <span className="block truncate text-sm text-foreground">
                                    {chat.title || tx("未命名会话")}
                                  </span>
                                  <span className="block text-xs text-muted-foreground">
                                    {tx(TELEGRAM_CHAT_TYPE_LABEL[chat.type] ?? "未知会话")} · {chat.id}
                                  </span>
                                </span>
                                <span className="shrink-0 text-xs font-medium text-primary">
                                  {tx("填入")}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                    <Field label={tx("解析模式")}>
                      <select
                        className={selectClass}
                        value={channelDraft.config.parse_mode ?? "HTML"}
                        onChange={(event) => setConfig("parse_mode", event.target.value)}
                      >
                        <option value="HTML">HTML</option>
                        <option value="MarkdownV2">MarkdownV2</option>
                      </select>
                    </Field>
                    <div className="flex items-end pb-3">
                      <CheckRow
                        label={tx("关闭链接预览")}
                        checked={channelDraft.config.disable_preview !== "false"}
                        onChange={(checked) => setConfig("disable_preview", String(checked))}
                      />
                    </div>
                  </div>
                ) : null}

                {channelDraft.type === "feishu" ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label={tx("Webhook 地址")}>
                      <Input
                        value={channelDraft.config.webhook_url ?? ""}
                        onChange={(event) => setConfig("webhook_url", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "webhook_url") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("加签密钥（可选）")}>
                      <Input
                        type="password"
                        value={channelDraft.config.secret ?? ""}
                        onChange={(event) => setConfig("secret", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "secret") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                  </div>
                ) : null}

                {channelDraft.type === "dingtalk" ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label={tx("Webhook 地址")}>
                      <Input
                        value={channelDraft.config.webhook_url ?? ""}
                        onChange={(event) => setConfig("webhook_url", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "webhook_url") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("加签密钥（可选）")}>
                      <Input
                        type="password"
                        value={channelDraft.config.secret ?? ""}
                        onChange={(event) => setConfig("secret", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "secret") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("@ 手机号（逗号分隔）")}>
                      <Input
                        value={channelDraft.config.at_mobiles ?? ""}
                        onChange={(event) => setConfig("at_mobiles", event.target.value)}
                      />
                    </Field>
                    <div className="flex items-end pb-3">
                      <CheckRow
                        label={tx("@ 所有人")}
                        checked={channelDraft.config.at_all === "true"}
                        onChange={(checked) => setConfig("at_all", String(checked))}
                      />
                    </div>
                  </div>
                ) : null}

                {channelDraft.type === "bark" ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label={tx("服务器地址")} hint={tx("默认 https://api.day.app")}>
                      <Input
                        value={channelDraft.config.server_url ?? ""}
                        onChange={(event) => setConfig("server_url", event.target.value)}
                      />
                    </Field>
                    <Field label={tx("Device Key")}>
                      <Input
                        type="password"
                        value={channelDraft.config.device_key ?? ""}
                        onChange={(event) => setConfig("device_key", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "device_key") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("分组（可选）")}>
                      <Input
                        value={channelDraft.config.group ?? ""}
                        onChange={(event) => setConfig("group", event.target.value)}
                      />
                    </Field>
                    <Field label={tx("铃声（可选）")}>
                      <Input
                        value={channelDraft.config.sound ?? ""}
                        onChange={(event) => setConfig("sound", event.target.value)}
                      />
                    </Field>
                  </div>
                ) : null}

                {channelDraft.type === "webhook" ? (
                  <div className="space-y-4">
                    <Field label={tx("Webhook 地址")}>
                      <Input
                        value={channelDraft.config.url ?? ""}
                        onChange={(event) => setConfig("url", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "url") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("自定义 headers（JSON 对象，可选）")}>
                      <textarea
                        className={areaClass}
                        rows={3}
                        value={channelDraft.config.headers ?? ""}
                        onChange={(event) => setConfig("headers", event.target.value)}
                        placeholder={channelMaskedPlaceholder(editingChannel, "headers") ?? '{"X-Token":"..."}'}
                      />
                    </Field>
                    <Field label={tx("HMAC 密钥（可选）")}>
                      <Input
                        type="password"
                        value={channelDraft.config.hmac_secret ?? ""}
                        onChange={(event) => setConfig("hmac_secret", event.target.value)}
                        placeholder={
                          editingChannelId == null
                            ? undefined
                            : channelMaskedPlaceholder(editingChannel, "hmac_secret") ??
                              tx("留空表示不修改")
                        }
                      />
                    </Field>
                    <Field label={tx("Body 模板（可选，JSON）")} hint={tx("占位符：{title} {body} {event} {job_id} {link}")}>
                      <textarea
                        className={areaClass}
                        rows={4}
                        value={channelDraft.config.body_template ?? ""}
                        onChange={(event) => setConfig("body_template", event.target.value)}
                        placeholder='{"text":"{title}: {body}"}'
                      />
                    </Field>
                  </div>
                ) : null}

                <div className="grid gap-4 md:grid-cols-4">
                  <Field label={tx("最大尝试次数")}>
                    <Input
                      type="number"
                      min={1}
                      max={10}
                      value={channelDraft.maxAttempts}
                      onChange={(event) =>
                        setChannelDraft((draft) => (draft ? { ...draft, maxAttempts: event.target.value } : draft))
                      }
                    />
                  </Field>
                  <Field label={tx("退避基数（秒）")}>
                    <Input
                      type="number"
                      min={1}
                      max={3600}
                      value={channelDraft.backoffSeconds}
                      onChange={(event) =>
                        setChannelDraft((draft) => (draft ? { ...draft, backoffSeconds: event.target.value } : draft))
                      }
                    />
                  </Field>
                  <Field label={tx("超时（秒）")}>
                    <Input
                      type="number"
                      min={1}
                      max={60}
                      value={channelDraft.timeoutSeconds}
                      onChange={(event) =>
                        setChannelDraft((draft) => (draft ? { ...draft, timeoutSeconds: event.target.value } : draft))
                      }
                    />
                  </Field>
                  <div className="flex flex-col justify-end gap-1 pb-3">
                    <CheckRow
                      label={tx("使用全局代理")}
                      checked={channelDraft.config.use_proxy !== "false"}
                      onChange={(checked) => setConfig("use_proxy", String(checked))}
                    />
                    <span className="text-xs text-muted-foreground">
                      {tx("关闭后该渠道直连，不走全局/环境代理")}
                    </span>
                  </div>
                </div>

                {editingChannelId != null &&
                ["feishu", "dingtalk", "webhook"].includes(channelDraft.type) ? (
                  <CheckRow
                    label={tx("清空可选密钥（飞书/钉钉加签、Webhook HMAC）")}
                    checked={channelDraft.clearSecret}
                    onChange={(checked) =>
                      setChannelDraft((draft) => (draft ? { ...draft, clearSecret: checked } : draft))
                    }
                  />
                ) : null}

                {channelError ? (
                  <p ref={channelErrorRef} role="alert" className="text-sm text-destructive">
                    {channelError}
                  </p>
                ) : null}

                <div className="flex gap-2">
                  <Button onClick={saveChannel} disabled={savingChannel}>
                    {savingChannel ? tx("保存中…") : tx("保存渠道")}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setChannelDraft(null);
                      resetChatLookup();
                    }}
                  >
                    {tx("取消")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {(channels.data ?? []).length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                {tx("还没有通知渠道。先新建一个，再发测试消息。")}
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {(channels.data ?? []).map((channel) => (
                <Card key={channel.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="text-base">{channel.name}</CardTitle>
                        <CardDescription>
                          {channel.type} · {channel.enabled ? tx("启用") : tx("停用")}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {channel.enabled ? tx("已启用") : tx("已停用")}
                        </span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={channel.enabled}
                          aria-label={tx("启用渠道")}
                          disabled={togglingId === channel.id}
                          onClick={() => toggleChannel(channel)}
                          className={`relative h-6 w-11 rounded-full transition-colors ${
                            channel.enabled ? "bg-primary" : "bg-muted-foreground/30"
                          } disabled:opacity-50`}
                        >
                          <span
                            className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-[left] ${
                              channel.enabled ? "left-[22px]" : "left-0.5"
                            }`}
                          />
                        </button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-muted-foreground">
                      {tx("重试 {n} 次 / 退避 {b}s / 超时 {t}s", {
                        n: channel.max_attempts,
                        b: channel.backoff_seconds,
                        t: channel.timeout_seconds,
                      })}
                    </p>
                    {channel.last_error ? (
                      <p className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                        {channel.last_error}
                      </p>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => testChannel(channel)} disabled={testingId === channel.id}>
                        <Send /> {testingId === channel.id ? tx("发送中…") : tx("测试")}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => openEditChannel(channel)}>
                        {tx("编辑")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteChannel(channel)}>
                        <Trash2 /> {tx("删除")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {tab === "rules" ? (
        <div className="space-y-4">
          {ruleDraft ? (
            <Card>
              <CardHeader>
                <CardTitle>{ruleDraft.id == null ? tx("新建规则") : tx("编辑规则")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label={tx("名称")}>
                    <Input
                      value={ruleDraft.name}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, name: event.target.value } : draft))}
                    />
                  </Field>
                  <div className="flex items-end pb-3">
                    <CheckRow
                      label={tx("启用")}
                      checked={ruleDraft.enabled}
                      onChange={(checked) => setRuleDraft((draft) => (draft ? { ...draft, enabled: checked } : draft))}
                    />
                  </div>
                </div>

                <Field label={tx("事件")}>
                  <div className="flex flex-wrap gap-4">
                    {EVENT_OPTIONS.map((event) => (
                      <CheckRow
                        key={event.value}
                        label={tx(event.label)}
                        checked={ruleDraft.events.includes(event.value)}
                        onChange={(checked) =>
                          setRuleDraft((draft) =>
                            draft
                              ? {
                                  ...draft,
                                  events: checked
                                    ? [...draft.events, event.value]
                                    : draft.events.filter((value) => value !== event.value),
                                }
                              : draft,
                          )
                        }
                      />
                    ))}
                  </div>
                </Field>

                <div className="grid gap-4 md:grid-cols-3">
                  <Field label={tx("进度间隔（秒）")}>
                    <Input
                      type="number"
                      min={60}
                      value={ruleDraft.interval}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, interval: event.target.value } : draft))}
                    />
                  </Field>
                  <Field label={tx("每摘要最多任务数")}>
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      value={ruleDraft.maxJobs}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, maxJobs: event.target.value } : draft))}
                    />
                  </Field>
                  <Field label={tx("任务类型过滤（逗号分隔）")} hint={tx("空=全部；canvas.node 需显式填写。")}>
                    <Input
                      value={ruleDraft.jobKinds}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, jobKinds: event.target.value } : draft))}
                      placeholder="video.motion, canvas.run"
                    />
                  </Field>
                </div>

                <Field
                  label={tx("投递渠道")}
                  hint={tx("一个规则可以同时投多个渠道；需要不同事件或间隔时，请分别建规则。")}
                >
                  <div className="space-y-3">
                    {Object.entries(groupedChannels).map(([type, list]) => (
                      <div key={type}>
                        <p className="mb-2 text-xs font-medium text-muted-foreground">
                          {CHANNEL_TYPE_LABEL[type] ?? type}
                        </p>
                        <div className="flex flex-wrap gap-4">
                          {list.map((channel) => (
                            <CheckRow
                              key={channel.id}
                              label={channel.name}
                              checked={ruleDraft.channelIds.includes(channel.id)}
                              onChange={(checked) =>
                                setRuleDraft((draft) =>
                                  draft
                                    ? {
                                        ...draft,
                                        channelIds: checked
                                          ? [...draft.channelIds, channel.id]
                                          : draft.channelIds.filter((id) => id !== channel.id),
                                      }
                                    : draft,
                                )
                              }
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                    {(channels.data ?? []).length === 0 ? (
                      <span className="text-xs text-muted-foreground">{tx("先创建渠道")}</span>
                    ) : null}
                  </div>
                </Field>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="flex items-end pb-3">
                    <CheckRow
                      label={tx("启用静默时段")}
                      checked={ruleDraft.quietEnabled}
                      onChange={(checked) => setRuleDraft((draft) => (draft ? { ...draft, quietEnabled: checked } : draft))}
                    />
                  </div>
                  <Field label={tx("静默开始")}>
                    <Input
                      type="time"
                      value={ruleDraft.quietStart}
                      disabled={!ruleDraft.quietEnabled}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, quietStart: event.target.value } : draft))}
                    />
                  </Field>
                  <Field label={tx("静默结束")}>
                    <Input
                      type="time"
                      value={ruleDraft.quietEnd}
                      disabled={!ruleDraft.quietEnabled}
                      onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, quietEnd: event.target.value } : draft))}
                    />
                  </Field>
                </div>
                <Field label={tx("时区")}>
                  <Input
                    value={ruleDraft.quietTimezone}
                    disabled={!ruleDraft.quietEnabled}
                    onChange={(event) => setRuleDraft((draft) => (draft ? { ...draft, quietTimezone: event.target.value } : draft))}
                  />
                </Field>

                <div className="flex items-center gap-4">
                  <CheckRow
                    label={tx("完成消息带输出链接")}
                    checked={ruleDraft.includeOutputs}
                    onChange={(checked) => setRuleDraft((draft) => (draft ? { ...draft, includeOutputs: checked } : draft))}
                  />
                </div>

                <details className="rounded-xl border border-border p-3">
                  <summary className="cursor-pointer text-sm font-medium">{tx("高级：模板覆盖")}</summary>
                  <div className="mt-3 grid gap-3">
                    <Field label={tx("成功模板")}>
                      <textarea
                        className={areaClass}
                        rows={3}
                        value={ruleDraft.templateSucceeded}
                        onChange={(event) =>
                          setRuleDraft((draft) => (draft ? { ...draft, templateSucceeded: event.target.value } : draft))
                        }
                      />
                    </Field>
                    <Field label={tx("失败模板")}>
                      <textarea
                        className={areaClass}
                        rows={3}
                        value={ruleDraft.templateFailed}
                        onChange={(event) =>
                          setRuleDraft((draft) => (draft ? { ...draft, templateFailed: event.target.value } : draft))
                        }
                      />
                    </Field>
                    <Field
                      label={tx("进度模板")}
                      hint={tx("可用占位符：{count} {running} {queued} {jobs} {link}")}
                    >
                      <textarea
                        className={areaClass}
                        rows={3}
                        value={ruleDraft.templateProgress}
                        onChange={(event) =>
                          setRuleDraft((draft) => (draft ? { ...draft, templateProgress: event.target.value } : draft))
                        }
                      />
                    </Field>
                  </div>
                </details>

                {ruleError ? (
                  <p ref={ruleErrorRef} role="alert" className="text-sm text-destructive">
                    {ruleError}
                  </p>
                ) : null}

                <div className="flex gap-2">
                  <Button onClick={saveRule} disabled={savingRule}>
                    {savingRule ? tx("保存中…") : tx("保存规则")}
                  </Button>
                  <Button variant="outline" onClick={() => setRuleDraft(null)}>
                    {tx("取消")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {(rules.data ?? []).length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                {tx("还没有规则。新建规则后，任务完成或运行中会收到通知。")}
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-3">
              {(rules.data ?? []).map((rule) => (
                <Card key={rule.id}>
                  <CardContent className="flex flex-wrap items-start justify-between gap-3 p-5">
                    <div className="min-w-0 space-y-1">
                      <p className="font-medium text-foreground">{rule.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {rule.events.join(" · ")} · {rule.progress_interval_seconds}s
                        {rule.job_kinds.length ? ` · ${rule.job_kinds.join(", ")}` : ""}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {tx("渠道：{names}", {
                          names:
                            rule.channel_ids
                              .map((id) => channelName(id))
                              .join(", ") || "—",
                        })}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <span className={`rounded-full px-2.5 py-1 text-xs ${statusClass(rule.enabled ? "sent" : "skipped")}`}>
                        {rule.enabled ? tx("启用") : tx("停用")}
                      </span>
                      <Button size="sm" variant="outline" onClick={() => openEditRule(rule)}>
                        {tx("编辑")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteRule(rule)}>
                        <Trash2 /> {tx("删除")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {tab === "deliveries" ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle>{tx("投递记录")}</CardTitle>
              <CardDescription>{tx("最近 100 条；失败可手动重试。")}</CardDescription>
            </div>
            <select
              className={`${selectClass} w-auto min-w-32`}
              value={deliveryStatus}
              onChange={(event) => setDeliveryStatus(event.target.value)}
            >
              <option value="">{tx("全部状态")}</option>
              <option value="pending">{tx("排队中")}</option>
              <option value="sending">{tx("发送中")}</option>
              <option value="sent">{tx("已发送")}</option>
              <option value="failed">{tx("失败")}</option>
              <option value="skipped">{tx("已跳过")}</option>
            </select>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {(deliveries.data?.items ?? []).length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">{tx("暂无投递记录")}</p>
            ) : (
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2">{tx("时间")}</th>
                    <th className="py-2">{tx("渠道")}</th>
                    <th className="py-2">{tx("事件")}</th>
                    <th className="py-2">{tx("标题")}</th>
                    <th className="py-2">{tx("状态")}</th>
                    <th className="py-2">{tx("尝试")}</th>
                    <th className="py-2">{tx("错误")}</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {(deliveries.data?.items ?? []).map((delivery) => (
                    <tr key={delivery.id} className="border-t border-border align-top">
                      <td className="py-2 pr-3 text-xs text-muted-foreground">{formatDate(delivery.created_at)}</td>
                      <td className="py-2 pr-3">{channelName(delivery.channel_id)}</td>
                      <td className="py-2 pr-3 text-xs">{delivery.event}</td>
                      <td className="max-w-64 py-2 pr-3">
                        <p className="truncate font-medium">{delivery.title}</p>
                        <p className="line-clamp-2 text-xs text-muted-foreground">{delivery.body}</p>
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(delivery.status)}`}>
                          {delivery.status}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-xs">{delivery.attempts}/{delivery.max_attempts}</td>
                      <td className="max-w-56 py-2 pr-3 text-xs text-destructive">{delivery.last_error ?? "—"}</td>
                      <td className="py-2">
                        {delivery.status === "failed" || delivery.status === "skipped" ? (
                          <Button size="sm" variant="outline" onClick={() => retryDelivery(delivery)}>
                            {tx("重试")}
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

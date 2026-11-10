import { AlertTriangle, CheckCircle2, Copy, Loader2, MinusCircle, RefreshCw, X, XCircle } from "lucide-react";
import { useState } from "react";

import type {
  WorkflowDoctorCheck,
  WorkflowDoctorItem,
  WorkflowDoctorProvider,
  WorkflowDoctorResult,
} from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { selectClass } from "@/components/ui/field";
import { useTx } from "@/i18n/tx";

const STATUS_STYLE: Record<string, string> = {
  pass: "text-success",
  warn: "text-warning",
  fail: "text-danger",
  skip: "text-muted-foreground",
};

function StatusIcon({ status }: { status: string }) {
  const Icon =
    status === "fail"
      ? XCircle
      : status === "warn"
        ? AlertTriangle
        : status === "skip"
          ? MinusCircle
          : CheckCircle2;
  return <Icon className={`size-4 shrink-0 ${STATUS_STYLE[status] ?? STATUS_STYLE.skip}`} aria-hidden="true" />;
}

interface Props {
  pack: string;
  result?: WorkflowDoctorResult;
  error?: Error | null;
  loading: boolean;
  providers: WorkflowDoctorProvider[];
  providerId?: number;
  onProviderChange: (id: number) => void;
  onRetry: () => void;
  onClose: () => void;
}

export function WorkflowDoctorPanel({
  pack,
  result,
  error,
  loading,
  providers,
  providerId,
  onProviderChange,
  onRetry,
  onClose,
}: Props) {
  const tx = useTx();
  const [copied, setCopied] = useState(false);

  const statusLabel = (status: string) =>
    tx(
      status === "fail"
        ? "失败"
        : status === "warn"
          ? "警告"
          : status === "skip"
            ? "跳过"
            : "通过",
    );

  const copyJson = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const summary = result?.summary ?? {};
  const items = (check: WorkflowDoctorCheck) => check.items ?? [];

  return (
    <Card aria-live="polite">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <div className="flex min-w-0 flex-col gap-1">
          <CardTitle className="flex flex-wrap items-center gap-2 text-base">
            <span className="truncate">{pack}</span>
            {result && <StatusIcon status={result.status} />}
            {result && (
              <span className={`text-sm font-medium ${STATUS_STYLE[result.status] ?? ""}`}>
                {statusLabel(result.status)}
              </span>
            )}
          </CardTitle>
          {result?.provider && (
            <span className="text-xs text-muted-foreground">
              {result.provider.name} · {result.provider.base_url}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {providers.length > 1 && (
            <select
              className={`${selectClass} h-9 w-auto max-w-44 text-xs`}
              aria-label={tx("体检服务")}
              value={providerId ?? providers[0]?.id ?? ""}
              onChange={(event) => onProviderChange(Number(event.target.value))}
              disabled={loading}
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          )}
          <Button variant="ghost" size="icon" onClick={onRetry} disabled={loading} title={tx("重新体检")}>
            {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          </Button>
          <Button variant="ghost" size="icon" onClick={copyJson} disabled={!result} title={tx("复制 JSON")}>
            <Copy />
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose} title={tx("关闭体检")}>
            <X />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {loading && (
          <p role="status" className="text-sm text-muted-foreground">
            {tx("体检中…")}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error.message}
          </p>
        )}
        {!loading && !error && result && (
          <>
            <p className="text-xs text-muted-foreground">
              {tx("通过")} {summary.pass ?? 0} · {tx("警告")} {summary.warn ?? 0} · {tx("失败")} {summary.fail ?? 0} ·{" "}
              {tx("跳过")} {summary.skip ?? 0}
            </p>
            <div className="flex flex-col gap-2">
              {result.checks.map((check) => (
                <div key={check.id} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusIcon status={check.status} />
                    <span className="font-medium">{tx(check.label)}</span>
                    <span className={`text-xs ${STATUS_STYLE[check.status] ?? ""}`}>{statusLabel(check.status)}</span>
                    {check.detail && <span className="text-xs text-muted-foreground">{check.detail}</span>}
                  </div>
                  {items(check).length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1.5 pl-6">
                      {items(check).map((item: WorkflowDoctorItem) => (
                        <li key={`${check.id}:${item.name}`} className="text-xs">
                          <div className="flex items-start gap-1.5">
                            <StatusIcon status={item.status} />
                            <span className="min-w-0 break-all">{item.name}</span>
                            {item.optional && (
                              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                {tx("可选")}
                              </span>
                            )}
                          </div>
                          {item.hint && <div className="pl-5 text-muted-foreground">{item.hint}</div>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
            {copied && <p className="text-xs text-success">{tx("已复制")}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

"""通知消息渲染：中英文完成/失败/画布汇总/进度摘要。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from liberastra.models import Job
from liberastra.services.notifications.adapters import NotificationMessage

_SECRET_QUERY = re.compile(
    r"(?i)(token|key|secret|sign|password|access_token)=([^&\s]+)"
)
_BEARER = re.compile(r"(?i)(authorization:\s*bearer\s+|bearer\s+)[^\s,;]+")
_URL = re.compile(r"https?://[^\s]+")

_STRINGS = {
    "zh-CN": {
        "succeeded": "成功",
        "failed": "失败",
        "canceled": "已取消",
        "running": "运行中",
        "queued": "排队",
        "status": "状态",
        "elapsed": "耗时",
        "outputs": "输出",
        "error": "错误",
        "view_job": "查看任务",
        "view_canvas": "查看画布",
        "canvas_succeeded": "画布完成",
        "canvas_failed": "画布失败",
        "canvas_canceled": "画布已取消",
        "canvas_summary": "画布「{name}」：成功 {ok} 个节点，失败 {failed} 个节点",
        "more": "还有 {n} 个任务…",
        "test_title": "LiberAstra 通知测试",
        "test_body": "这是一条测试通知。能收到说明渠道配置有效。",
    },
    "en": {
        "succeeded": "Succeeded",
        "failed": "Failed",
        "canceled": "Canceled",
        "running": "Running",
        "queued": "Queued",
        "status": "Status",
        "elapsed": "Duration",
        "outputs": "Outputs",
        "error": "Error",
        "view_job": "View job",
        "view_canvas": "View canvas",
        "canvas_succeeded": "Canvas completed",
        "canvas_failed": "Canvas failed",
        "canvas_canceled": "Canvas canceled",
        "canvas_summary": 'Canvas "{name}": {ok} nodes succeeded, {failed} failed',
        "more": "{n} more jobs…",
        "test_title": "LiberAstra notification test",
        "test_body": "This is a test notification. If you can read this, the channel is working.",
    },
}


def strings(language: str) -> dict[str, str]:
    return _STRINGS.get(language, _STRINGS["zh-CN"])


def redact(text: str | None, limit: int = 300) -> str:
    value = str(text or "").strip()
    value = _SECRET_QUERY.sub(r"\1=***", value)
    value = _BEARER.sub(r"\1***", value)
    value = _URL.sub(lambda match: _mask_url(match.group(0)), value)
    return " ".join(value.split())[:limit]


def _mask_url(value: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return "***"
    tail = "/***" if parts.path or parts.query else ""
    return f"{parts.scheme}://{parts.netloc}{tail}"


def job_name(job: Job) -> str:
    params = job.params or {}
    for key in ("node_label", "label", "workflow", "model"):
        value = params.get(key)
        if value:
            return str(value)[:80]
    return str(job.function or job.model or job.kind)[:80]


def elapsed_text(job: Job) -> str:
    end = job.finished_at or job.updated_at or job.created_at
    seconds = max(0, int((end - job.created_at).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def output_count(job: Job) -> int:
    return len(job.outputs or [])


def _link(base_url: str | None, path: str) -> str | None:
    if not base_url:
        return None
    return f"{base_url.rstrip('/')}{path}"


def render_terminal(
    job: Job,
    language: str,
    base_url: str | None = None,
    *,
    include_outputs: bool = True,
) -> NotificationMessage:
    t = strings(language)
    status_text = t.get(job.status, job.status)
    name = job_name(job)
    title = f"[{status_text}] {name}"
    lines = [
        f"{t['status']}: {status_text}",
        f"{t['elapsed']}: {elapsed_text(job)}",
    ]
    if job.model:
        lines.append(f"Model: {job.model}")
    if include_outputs:
        lines.append(f"{t['outputs']}: {output_count(job)}")
    if job.status == "failed" and job.error:
        lines.append(f"{t['error']}: {redact(job.error)}")
    link = _link(base_url, f"/jobs/{job.id}") if include_outputs else None
    if link:
        lines.append(f"{t['view_job']}: {link}")
    return NotificationMessage(
        title=title,
        body="\n".join(lines),
        event=f"job.{job.status}",
        job_id=job.id,
        link=link,
        payload={"job_kind": job.kind},
    )


def render_canvas_run(
    job: Job,
    language: str,
    base_url: str | None = None,
    *,
    include_outputs: bool = True,
) -> NotificationMessage:
    t = strings(language)
    params = job.params or {}
    name = str(params.get("canvas_name") or params.get("canvas_id") or "Canvas")[:80]
    ok = int(params.get("success_count") or 0)
    failed = int(params.get("failed_count") or 0)
    status_text = t.get(job.status, job.status)
    key = f"canvas_{job.status}"
    title = f"[{t.get(key, status_text)}] {name}"
    lines = [t["canvas_summary"].format(name=name, ok=ok, failed=failed)]
    duration_ms = params.get("duration_ms")
    if duration_ms is not None:
        lines.append(f"{t['elapsed']}: {int(duration_ms) / 1000:.1f}s")
    if job.error:
        lines.append(f"{t['error']}: {redact(job.error)}")
    link = None
    canvas_id = params.get("canvas_id")
    if include_outputs and canvas_id:
        link = _link(base_url, f"/canvas/{canvas_id}")
        if link:
            lines.append(f"{t['view_canvas']}: {link}")
    return NotificationMessage(
        title=title,
        body="\n".join(lines),
        event=f"job.{job.status}",
        job_id=job.id,
        link=link,
        payload={"job_kind": job.kind, "canvas_id": canvas_id},
    )


@dataclass
class ProgressEntry:
    name: str
    progress: float
    step: str = ""
    elapsed: str = ""


def render_progress(
    entries: list[ProgressEntry],
    language: str,
    base_url: str | None = None,
    *,
    running: int = 0,
    queued: int = 0,
    hidden: int = 0,
) -> NotificationMessage:
    t = strings(language)
    title = f"[LiberAstra] {t['running']} {running} · {t['queued']} {queued}"
    lines = []
    for entry in entries:
        percent = max(0, min(100, round(entry.progress * 100)))
        detail = f" · {entry.step}" if entry.step else ""
        elapsed = f" · {entry.elapsed}" if entry.elapsed else ""
        lines.append(f"· {entry.name} {percent}%{detail}{elapsed}")
    if hidden > 0:
        lines.append(t["more"].format(n=hidden))
    link = _link(base_url, "/jobs")
    if link:
        lines.append(f"{t['view_job']}: {link}")
    return NotificationMessage(
        title=title,
        body="\n".join(lines),
        event="job.progress",
        link=link,
        payload={"running": running, "queued": queued},
    )


def render_test(language: str) -> NotificationMessage:
    t = strings(language)
    return NotificationMessage(title=t["test_title"], body=t["test_body"], event="test")


def format_elapsed(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None:
        return ""
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m{seconds:02d}s" if minutes < 60 else f"{minutes // 60}h{minutes % 60:02d}m"

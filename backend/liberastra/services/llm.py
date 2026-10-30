"""LLM 能力服务：选择 Provider、llm.chat 任务 runner。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job, Provider
from liberastra.providers.catalog import read_catalog
from liberastra.services.providers import build_llm_adapter


def pick_llm_provider(db: Session, provider_id: int | None = None) -> Provider:
    if provider_id is not None:
        record = db.get(Provider, provider_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider 不存在")
        if not record.enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider 已停用")
        if "llm" not in record.capabilities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="该 Provider 不具备 LLM 能力"
            )
        return record

    for record in db.scalars(select(Provider).where(Provider.enabled.is_(True))).all():
        if "llm" in record.capabilities:
            return record
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="尚未配置任何启用的 LLM Provider"
    )


async def run_chat_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = db.get(Provider, job.provider_id) if job.provider_id else None
    if provider is None:
        raise RuntimeError("任务缺少 Provider")
    adapter = build_llm_adapter(provider, db=db)
    ctx.report(db, job, progress=0.1, step="chat")
    text = await adapter.chat(
        model=job.model or "",
        messages=job.params.get("messages", []),
        **_chat_options(provider, job.model or "", job.params.get("options") or {}),
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "text", "content": text}]


def _chat_options(provider: Provider, model: str, options: dict[str, Any]) -> dict[str, Any]:
    """请求里已经带了 max_tokens 就尊重请求。否则用模型设置里的最大输出。"""
    if options.get("max_tokens"):
        return options
    for item in read_catalog(provider.extra, provider.type):
        if item.get("id") != model:
            continue
        tokens = (item.get("params") or {}).get("max_output")
        if tokens:
            return {**options, "max_tokens": int(tokens)}
    return options


def register_llm_jobs(manager: JobManager) -> None:
    manager.register("llm.chat", run_chat_job)

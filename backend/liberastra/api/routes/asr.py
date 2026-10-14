"""ASR 路由：语音转文字（multipart 上传，走 Job 队列）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job
from liberastra.schemas.job import JobOut
from liberastra.services.providers import pick_provider
from liberastra.storage import save_upload

router = APIRouter(prefix="/asr", tags=["asr"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def transcribe(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    file: Annotated[UploadFile, File()],
    provider_id: Annotated[int | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    task: Annotated[str, Form(pattern="^(transcribe|translate)$")] = "transcribe",
    model: Annotated[str | None, Form()] = None,
    formats: Annotated[str, Form()] = "txt,json,srt,vtt",
    wait: bool = False,
) -> Job:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大")

    provider = pick_provider(db, "asr", provider_id)
    rel_path = save_upload(file.filename or "audio.bin", content)

    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="asr.transcribe",
        params={
            "file_path": rel_path,
            "language": language,
            "task": task,
            "formats": [f.strip() for f in formats.split(",") if f.strip()],
        },
        provider_id=provider.id,
        model=model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job

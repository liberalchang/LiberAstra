"""TTS 路由：文字转语音（走 Job 队列）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job, Voice
from liberastra.schemas.job import JobOut
from liberastra.schemas.tts import TTSRequest
from liberastra.services.providers import pick_provider

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def synthesize(
    body: TTSRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "tts", body.provider_id)

    voice_name = body.voice
    options = dict(body.options)
    if body.voice_record_id is not None:
        record = db.get(Voice, body.voice_record_id)
        if record is None or record.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音色不存在")
        voice_name = record.voice_id or record.name
        # 参考音频用来模仿音色。voice_id 可能是编号，不能当成语言。
        if record.ref_audio_path and "ref_audio" not in options:
            options["ref_audio"] = record.ref_audio_path
    if not voice_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 voice 或 voice_record_id"
        )

    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="tts.synthesize",
        params={
            "text": body.text,
            "voice": voice_name,
            "format": body.format,
            "options": options,
        },
        provider_id=provider.id,
        model=body.model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job

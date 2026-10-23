"""TTS 路由：文字转语音（走 Job 队列）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.routes.images import _validate_workflow_for
from liberastra.api.utils import wait_for_job
from liberastra.models import Job, Voice
from liberastra.providers.base import ProviderError
from liberastra.schemas.job import JobOut
from liberastra.schemas.tts import TTSPreviewRequest, TTSRequest
from liberastra.services.providers import build_tts_adapter, pick_provider

router = APIRouter(prefix="/tts", tags=["tts"])

# 试听只覆盖能当场返回音频的服务。音色库（Liber Speech）直接播参考音频，Comfy 工作流太慢。
_PREVIEW_TYPES = frozenset({"edge_tts", "openai_tts"})


@router.post("/preview")
async def preview(body: TTSPreviewRequest, user: CurrentUser, db: DbSession) -> Response:
    """用当前音色合成一句短文本并直接返回 mp3，供页面试听。"""
    provider = pick_provider(db, "tts", body.provider_id)
    if provider.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="服务不存在")
    if provider.type not in _PREVIEW_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前配音服务不支持试听")
    text = body.text.strip()
    voice = body.voice.strip()
    if not text or not voice:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="试听需要音色和文本")
    adapter = build_tts_adapter(provider, db=db)
    try:
        audio = await adapter.synthesize(text=text, voice=voice, fmt="mp3")
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


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

    params: dict = {
        "text": body.text,
        "voice": voice_name,
        "format": body.format,
        "options": options,
    }
    if provider.type == "comfyui":
        # comfy 语音工作流：voice 可为空，text/voice/ref_audio 由 runner 按 manifest 注入
        _validate_workflow_for(db, provider, body.workflow)
        params["workflow"] = body.workflow
        params["inputs"] = body.inputs
    elif not voice_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 voice 或 voice_record_id"
        )

    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="tts.synthesize",
        params=params,
        provider_id=provider.id,
        model=body.model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job

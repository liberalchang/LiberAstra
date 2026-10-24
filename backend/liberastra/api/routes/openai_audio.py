"""OpenAI 兼容子集（/v1）：audio/speech、audio/transcriptions。

同步接口：直接调用默认 Provider 适配器，便于现有 Agent 和 SDK 接入。
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, Response

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.media.subtitles import to_srt, to_vtt
from liberastra.providers.base import ProviderError
from liberastra.schemas.tts import OpenAISpeechRequest
from liberastra.services.providers import build_asr_adapter, build_tts_adapter, pick_provider
from liberastra.storage import resolve, save_upload

router = APIRouter(prefix="/v1", tags=["openai-compat"])

_MIME_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg_opus": "audio/ogg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
}


@router.post("/audio/speech")
async def speech(body: OpenAISpeechRequest, user: CurrentUser, db: DbSession) -> Response:
    provider = pick_provider(db, "tts")
    adapter = build_tts_adapter(provider, db=db)
    options = {"speed": body.speed} if body.speed else {}
    try:
        audio = await adapter.synthesize(
            text=body.input,
            voice=body.voice,
            model=body.model,
            fmt=body.response_format,
            **options,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type=_MIME_BY_FORMAT.get(body.response_format, "application/octet-stream"),
    )


@router.post("/audio/transcriptions")
async def transcriptions(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = "whisper-1",
    response_format: Annotated[str, Form()] = "json",
    language: Annotated[str | None, Form()] = None,
) -> Response:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")

    provider = pick_provider(db, "asr")
    adapter = build_asr_adapter(provider, db=db)
    rel_path = save_upload(file.filename or "audio.bin", content)
    try:
        result = await adapter.transcribe(
            file_path=str(resolve(rel_path)), language=language, model=model
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if response_format == "srt":
        return PlainTextResponse(to_srt(result), media_type="application/x-subrip")
    if response_format == "vtt":
        return PlainTextResponse(to_vtt(result), media_type="text/vtt")
    if response_format == "text":
        return PlainTextResponse(result.text)
    return Response(
        content=json.dumps(
            {
                "text": result.text,
                "language": result.language,
                "segments": [
                    {"start": s.start, "end": s.end, "text": s.text} for s in result.segments
                ],
            },
            ensure_ascii=False,
        ),
        media_type="application/json",
    )

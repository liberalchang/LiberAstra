"""换音路由：上传音频/视频、音色和可选 srt，走 vc.convert 任务。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.media import ffmpeg
from liberastra.models import Job, Voice
from liberastra.providers.speech.liber_speech import canonical_vc_model
from liberastra.schemas.job import JobOut
from liberastra.services.providers import pick_provider
from liberastra.services.vc import MAX_MEDIA_SECONDS
from liberastra.storage import resolve, save_upload

router = APIRouter(prefix="/vc", tags=["vc"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB
MAX_SUBTITLE_BYTES = 2 * 1024 * 1024  # 2MB


def _remove(rel_path: str | None) -> None:
    if not rel_path:
        return
    try:
        resolve(rel_path).unlink(missing_ok=True)
    except ValueError:
        return


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def convert(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    file: Annotated[UploadFile, File()],
    voice_record_id: Annotated[int, Form()],
    provider_id: Annotated[int | None, Form()] = None,
    model: Annotated[str | None, Form()] = None,
    format: Annotated[str, Form(pattern="^(mp3|wav)$")] = "mp3",
    separate_bgm: Annotated[bool, Form()] = False,
    subtitle: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str | None, Form()] = None,
    burn_subtitles: Annotated[bool, Form()] = False,
    subtitle_size: Annotated[float, Form(ge=0, le=200)] = 0,
    subtitle_color: Annotated[str, Form(max_length=16)] = "",
    wait: bool = False,
) -> Job:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大")

    provider = pick_provider(db, "vc", provider_id)
    record = db.get(Voice, voice_record_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音色不存在")
    if not record.ref_audio_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音色没有参考音频")

    try:
        chosen_model = canonical_vc_model(model or "") or None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    rel_path = save_upload(file.filename or "vc-input.bin", content)
    subtitle_rel: str | None = None
    try:
        if subtitle is not None and subtitle.filename:
            if Path(subtitle.filename).suffix.lower() != ".srt":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="字幕只支持 srt")
            subtitle_content = await subtitle.read()
            if len(subtitle_content) > MAX_SUBTITLE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="字幕文件过大",
                )
            subtitle_rel = save_upload(subtitle.filename, subtitle_content)

        source = resolve(rel_path)
        duration = await ffmpeg.probe_duration(source)
        if duration > MAX_MEDIA_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"换音素材不能超过 {MAX_MEDIA_SECONDS // 60} 分钟",
            )
        is_video = await ffmpeg.has_video_stream(source)
        if not is_video and not await ffmpeg.has_audio_stream(source):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件没有音轨")
        if burn_subtitles and not is_video:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有视频输入才能烧录字幕",
            )
    except Exception:
        _remove(rel_path)
        _remove(subtitle_rel)
        raise

    params = {
        "file_path": rel_path,
        "voice_record_id": voice_record_id,
        "kind": "video" if is_video else "audio",
        "format": format,
        "separate_bgm": separate_bgm,
        "subtitle_path": subtitle_rel,
        "language": language,
        "burn_subtitles": burn_subtitles,
        "subtitle_size": subtitle_size,
        "subtitle_color": subtitle_color,
    }
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="vc.convert",
        params=params,
        provider_id=provider.id,
        model=chosen_model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job

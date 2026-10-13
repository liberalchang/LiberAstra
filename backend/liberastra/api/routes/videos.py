"""视频路由：快速创作、图生视频、数字人口播、动作迁移、自定义素材。"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job, User, Voice
from liberastra.schemas.job import JobOut
from liberastra.schemas.video import QuickVideoRequest
from liberastra.services.providers import pick_provider
from liberastra.storage import save_upload

router = APIRouter(prefix="/videos", tags=["videos"])


def _resolve_voice(db: Session, user: User, voice: str, voice_record_id: int | None) -> str:
    if voice_record_id is not None:
        record = db.get(Voice, voice_record_id)
        if record is None or record.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音色不存在")
        return record.voice_id or record.name
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 voice 或 voice_record_id"
        )
    return voice


def _submit(request: Request, db: Session, user: User, kind: str, params: dict, provider_id=None) -> Job:  # noqa: ANN001
    return request.app.state.jobs.submit(
        db, owner_id=user.id, kind=kind, params=params, provider_id=provider_id
    )


@router.post("/quick", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def quick(
    body: QuickVideoRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    voice = _resolve_voice(db, user, body.voice, body.voice_record_id)
    # 提前校验三类 Provider 可用，错误立即反馈而不是等任务失败
    pick_provider(db, "llm", body.llm_provider_id)
    pick_provider(db, "tts", body.tts_provider_id)
    pick_provider(db, "image", body.image_provider_id)

    job = _submit(
        request,
        db,
        user,
        "video.quick",
        {
            "topic": body.topic,
            "script": body.script,
            "split_mode": body.split_mode,
            "storyboard_count": body.storyboard_count,
            "aspect": body.aspect,
            "voice": voice,
            "style_prefix": body.style_prefix,
            "storyboard": body.storyboard,
            "storyboard_only": body.storyboard_only,
            "image_workflow": body.image_workflow,
            "image_inputs": body.image_inputs,
            "bgm_path": body.bgm_path,
            "bgm_volume": body.bgm_volume,
            "providers": {
                "llm": body.llm_provider_id,
                "tts": body.tts_provider_id,
                "image": body.image_provider_id,
            },
        },
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/i2v", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def i2v(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    image: Annotated[UploadFile, File()],
    workflow: Annotated[str, Form()],
    prompt: Annotated[str, Form()] = "",
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    image_path = save_upload(image.filename or "image.png", await image.read())
    job = _submit(
        request, db, user, "video.i2v",
        {
            "workflow": workflow,
            "prompt": prompt,
            "image_path": image_path,
            "inputs": _parse_inputs(inputs),
        },
        provider.id,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/avatar", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def avatar(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    image: Annotated[UploadFile, File()],
    text: Annotated[str, Form(min_length=1)],
    workflow: Annotated[str, Form()],
    voice: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    tts_provider_id: Annotated[int | None, Form()] = None,
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    voice_name = _resolve_voice(db, user, voice, voice_record_id)
    image_path = save_upload(image.filename or "person.png", await image.read())
    job = _submit(
        request, db, user, "video.avatar",
        {
            "workflow": workflow,
            "text": text,
            "voice": voice_name,
            "tts_provider_id": tts_provider_id,
            "image_path": image_path,
            "inputs": _parse_inputs(inputs),
        },
        provider.id,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/motion", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def motion(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    video: Annotated[UploadFile, File()],
    image: Annotated[UploadFile, File()],
    workflow: Annotated[str, Form()],
    prompt: Annotated[str, Form()] = "",
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    video_content = await video.read()
    if len(video_content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="参考视频过大")
    video_path = save_upload(video.filename or "ref.mp4", video_content)
    image_path = save_upload(image.filename or "target.png", await image.read())
    job = _submit(
        request, db, user, "video.motion",
        {
            "workflow": workflow,
            "prompt": prompt,
            "video_path": video_path,
            "image_path": image_path,
            "inputs": _parse_inputs(inputs),
        },
        provider.id,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/assets", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def custom_assets(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    images: Annotated[list[UploadFile], File()],
    topic: Annotated[str | None, Form()] = None,
    script: Annotated[str | None, Form()] = None,
    aspect: Annotated[str, Form(pattern="^(9:16|1:1|16:9)$")] = "9:16",
    voice: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    tts_provider_id: Annotated[int | None, Form()] = None,
    llm_provider_id: Annotated[int | None, Form()] = None,
    wait: bool = False,
) -> Job:
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传至少一张图片")
    if not script and not topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文案或主题")
    voice_name = _resolve_voice(db, user, voice, voice_record_id)

    image_paths = [
        save_upload(img.filename or f"asset_{i}.png", await img.read())
        for i, img in enumerate(images)
    ]
    job = _submit(
        request, db, user, "video.assets",
        {
            "image_paths": image_paths,
            "topic": topic,
            "script": script,
            "aspect": aspect,
            "voice": voice_name,
            "providers": {"tts": tts_provider_id, "llm": llm_provider_id},
        },
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


def _parse_inputs(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"inputs JSON 解析失败: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="inputs 必须是 JSON 对象")
    return value

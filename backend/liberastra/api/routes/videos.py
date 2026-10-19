"""视频路由：快速创作、图生视频、数字人口播、动作迁移、自定义素材。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job, User, Voice
from liberastra.pipelines.quick import resolve_quick_template
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
    voice = _resolve_voice(db, user, body.voice, body.voice_record_id) if (body.voice or body.voice_record_id) else ""
    # 提前校验 Provider 可用，错误立即反馈而不是等任务失败
    tts_provider = pick_provider(db, "tts", body.tts_provider_id)
    # 模板类型决定哪些 Provider 必需：插图要 image，视频要 video，静态两者都不用
    tpl = resolve_quick_template(body.template, body.aspect)
    # LLM：AI 写口播，或 image/video 模板下的画面提示词优化（可关，避免与 Guide 双重扩写）
    need_script_llm = body.storyboard is None and not body.script
    need_visual_llm = (
        body.storyboard is None
        and tpl.type in ("image", "video")
        and body.optimize_visuals
    )
    if need_script_llm or need_visual_llm:
        pick_provider(db, "llm", body.llm_provider_id)
    if tpl.type == "image" and tpl.needs_image:
        pick_provider(db, "image", body.image_provider_id)
    if tpl.type == "video":
        pick_provider(db, "video", body.video_provider_id)
    if tts_provider.type == "comfyui" and not body.tts_workflow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="配音 Provider 是 ComfyUI，需要选择语音工作流包"
        )

    job = _submit(
        request,
        db,
        user,
        "video.quick",
        {
            "topic": body.topic,
            "script": body.script,
            "title": body.title,
            "split_mode": body.split_mode,
            "storyboard_count": body.storyboard_count,
            "aspect": body.aspect,
            "voice": voice,
            "style_prefix": body.style_prefix,
            "storyboard": body.storyboard,
            "storyboard_only": body.storyboard_only,
            "optimize_visuals": body.optimize_visuals,
            "image_workflow": body.image_workflow,
            "image_inputs": body.image_inputs,
            "template": tpl.name,
            "tts_workflow": body.tts_workflow,
            "tts_inputs": body.tts_inputs,
            "video_workflow": body.video_workflow,
            "video_inputs": body.video_inputs,
            "bgm_path": body.bgm_path,
            "bgm_volume": body.bgm_volume,
            "show_title": body.show_title,
            "show_text": body.show_text,
            "show_subtitle": body.show_subtitle,
            "title_scale": body.title_scale,
            "text_scale": body.text_scale,
            "subtitle_size": body.subtitle_size,
            "subtitle_color": body.subtitle_color,
            "providers": {
                "llm": body.llm_provider_id,
                "tts": body.tts_provider_id,
                "image": body.image_provider_id,
                "video": body.video_provider_id,
            },
            "llm_model": body.llm_model,
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
    tts_workflow: Annotated[str | None, Form()] = None,
    tts_inputs: Annotated[str, Form()] = "{}",
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    voice_name = _resolve_voice(db, user, voice, voice_record_id) if (voice or voice_record_id) else ""
    image_path = save_upload(image.filename or "person.png", await image.read())
    job = _submit(
        request, db, user, "video.avatar",
        {
            "workflow": workflow,
            "text": text,
            "voice": voice_name,
            "tts_provider_id": tts_provider_id,
            "tts_workflow": tts_workflow,
            "tts_inputs": _parse_inputs(tts_inputs),
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
    title: Annotated[str, Form()] = "",
    duration: Annotated[int, Form()] = 30,
    aspect: Annotated[str, Form(pattern="^(9:16|1:1|16:9)$")] = "9:16",
    voice: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    animate: Annotated[bool, Form()] = False,
    video_workflow: Annotated[str | None, Form()] = None,
    video_inputs: Annotated[str, Form()] = "{}",
    tts_workflow: Annotated[str | None, Form()] = None,
    tts_inputs: Annotated[str, Form()] = "{}",
    analysis_image_workflow: Annotated[str | None, Form()] = None,
    analysis_video_workflow: Annotated[str | None, Form()] = None,
    analysis_inputs: Annotated[str, Form()] = "{}",
    analysis_provider_id: Annotated[int | None, Form()] = None,
    bgm_path: Annotated[str | None, Form()] = None,
    bgm_volume: Annotated[float, Form()] = 0.2,
    tts_provider_id: Annotated[int | None, Form()] = None,
    llm_provider_id: Annotated[int | None, Form()] = None,
    llm_model: Annotated[str, Form()] = "",
    video_provider_id: Annotated[int | None, Form()] = None,
    wait: bool = False,
) -> Job:
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传至少一个素材")
    if not script and not topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文案或主题")
    # 素材按扩展名分流：图片 / 视频
    image_ext = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    video_ext = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
    media: list[dict] = []
    for i, up in enumerate(images):
        ext = Path(up.filename or "").suffix.lower()
        if ext in image_ext:
            kind = "image"
        elif ext in video_ext:
            kind = "video"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的素材格式: {up.filename}",
            )
        rel = save_upload(up.filename or f"asset_{i}", await up.read())
        media.append({"path": rel, "kind": kind})
    has_image = any(m["kind"] == "image" for m in media)
    if animate and has_image:
        if not video_workflow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="素材动画需要选择 i2v 工作流包"
            )
        pick_provider(db, "video", video_provider_id)
    voice_name = _resolve_voice(db, user, voice, voice_record_id) if (voice or voice_record_id) else ""
    if analysis_image_workflow or analysis_video_workflow:
        pick_provider(db, "image", analysis_provider_id)

    job = _submit(
        request, db, user, "video.assets",
        {
            "media": media,
            "topic": topic,
            "script": script,
            "title": title,
            "duration": duration,
            "aspect": aspect,
            "voice": voice_name,
            "animate": animate,
            "video_workflow": video_workflow,
            "video_inputs": _parse_inputs(video_inputs),
            "tts_workflow": tts_workflow,
            "tts_inputs": _parse_inputs(tts_inputs),
            "analysis_image_workflow": analysis_image_workflow,
            "analysis_video_workflow": analysis_video_workflow,
            "analysis_inputs": _parse_inputs(analysis_inputs),
            "bgm_path": bgm_path,
            "bgm_volume": bgm_volume,
            "providers": {
                "tts": tts_provider_id,
                "llm": llm_provider_id,
                "video": video_provider_id,
                "analysis": analysis_provider_id,
            },
            "llm_model": llm_model,
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

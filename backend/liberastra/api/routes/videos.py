"""视频路由：快速创作、图生视频、数字人口播、动作迁移、自定义素材。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Character, Job, User, Voice
from liberastra.pipelines.quick import resolve_quick_template
from liberastra.pipelines.simple import analysis_pack_gaps
from liberastra.schemas.job import JobOut
from liberastra.schemas.video import QuickVideoRequest
from liberastra.services.characters import appearance_prefix, paths_for_task
from liberastra.services.providers import pick_llm_with_model, pick_provider
from liberastra.storage import save_upload

router = APIRouter(prefix="/videos", tags=["videos"])


def _form_bool(value: str, detail: str) -> bool:
    """表单里的布尔值。空字符串视为未传。"""
    text = value.strip().lower()
    if text in {"", "1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value[1:])


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


def _character(db: Session, user: User, character_id: int | None) -> Character | None:
    if character_id is None:
        return None
    record = db.get(Character, character_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return record


async def _image_or_character(
    image: UploadFile | None,
    character: Character | None,
    view: str,
    *,
    multi: bool,
) -> list[str]:
    """上传图优先；否则从角色库按视角取单人图，动作迁移可一次取正/侧/背。"""
    if image is not None and image.filename:
        content = await image.read()
        if content:
            return [save_upload(image.filename or "image.png", content)]
    if character is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片或选择角色")
    try:
        return paths_for_task(character, view, multi=multi)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
    # 模板类型决定哪些 Provider 必需：插图要 image，视频要 video，静态两者都不用
    tpl = resolve_quick_template(body.template, body.aspect)
    native_audio = body.audio_mode == "auto" and tpl.type == "video"
    voice = ""
    if not native_audio:
        if body.voice or body.voice_record_id:
            voice = _resolve_voice(db, user, body.voice, body.voice_record_id)
        tts_provider = pick_provider(db, "tts", body.tts_provider_id)
        if tts_provider.type == "comfyui" and not body.tts_workflow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配音 Provider 是 ComfyUI，需要选择语音工作流包",
            )
    # LLM：AI 写口播，或 image/video 模板下的画面提示词优化（用户开关；与包内 Guide 无关）
    need_script_llm = body.storyboard is None and not body.script
    need_visual_llm = (
        body.storyboard is None
        and tpl.type in ("image", "video")
        and body.optimize_visuals
    )
    if need_script_llm or need_visual_llm:
        # 未传 provider_id 时走系统默认 LLM
        pick_llm_with_model(db, body.llm_provider_id, body.llm_model or "")
    if tpl.type == "image" and tpl.needs_image:
        pick_provider(db, "image", body.image_provider_id)
    if tpl.type == "video":
        pick_provider(db, "video", body.video_provider_id)

    character = _character(db, user, body.character_id)
    style_prefix = f"{appearance_prefix(character)}{body.style_prefix}" if character else body.style_prefix
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
            "language": body.language,
            "style_prefix": style_prefix,
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
            "audio_mode": "auto" if native_audio else "custom",
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
    workflow: Annotated[str, Form()],
    image: Annotated[UploadFile | None, File()] = None,
    prompt: Annotated[str, Form()] = "",
    character_id: Annotated[int | None, Form()] = None,
    character_view: Annotated[str, Form()] = "front",
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    bgm_path: Annotated[str, Form()] = "",
    bgm_volume: Annotated[float, Form()] = 0.2,
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    paths = await _image_or_character(image, _character(db, user, character_id), character_view, multi=False)
    image_path = paths[0]
    job = _submit(
        request, db, user, "video.i2v",
        {
            "workflow": workflow,
            "prompt": prompt,
            "image_path": image_path,
            "inputs": _parse_inputs(inputs),
            "bgm_path": bgm_path.strip() or None,
            "bgm_volume": bgm_volume,
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
    text: Annotated[str, Form(min_length=1)],
    workflow: Annotated[str, Form()],
    image: Annotated[UploadFile | None, File()] = None,
    voice: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    language: Annotated[str, Form()] = "",
    character_id: Annotated[int | None, Form()] = None,
    tts_provider_id: Annotated[int | None, Form()] = None,
    tts_workflow: Annotated[str | None, Form()] = None,
    tts_inputs: Annotated[str, Form()] = "{}",
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    bgm_path: Annotated[str, Form()] = "",
    bgm_volume: Annotated[float, Form()] = 0.2,
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "video", provider_id)
    character = _character(db, user, character_id)
    if character and not voice and voice_record_id is None:
        voice_record_id = character.voice_record_id
        voice = character.voice_name or ""
    voice_name = _resolve_voice(db, user, voice, voice_record_id) if (voice or voice_record_id) else ""
    paths = await _image_or_character(image, character, "portrait", multi=False)
    image_path = paths[0]
    job = _submit(
        request, db, user, "video.avatar",
        {
            "workflow": workflow,
            "text": text,
            "voice": voice_name,
            "language": language,
            "tts_provider_id": tts_provider_id,
            "tts_workflow": tts_workflow,
            "tts_inputs": _parse_inputs(tts_inputs),
            "image_path": image_path,
            "inputs": _parse_inputs(inputs),
            "bgm_path": bgm_path.strip() or None,
            "bgm_volume": bgm_volume,
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
    workflow: Annotated[str, Form()],
    image: Annotated[UploadFile | None, File()] = None,
    prompt: Annotated[str, Form()] = "",
    character_id: Annotated[int | None, Form()] = None,
    provider_id: Annotated[int | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    audio_mode: Annotated[str, Form()] = "model",
    bgm_path: Annotated[str, Form()] = "",
    bgm_volume: Annotated[float, Form()] = 0.2,
    wait: bool = False,
) -> Job:
    if audio_mode not in {"model", "reference"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="声音来源只能是模型生成或参考视频原声",
        )
    provider = pick_provider(db, "video", provider_id)
    video_content = await video.read()
    if len(video_content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="参考视频过大")
    video_path = save_upload(video.filename or "ref.mp4", video_content)
    image_paths = await _image_or_character(image, _character(db, user, character_id), "front", multi=True)
    job = _submit(
        request, db, user, "video.motion",
        {
            "workflow": workflow,
            "prompt": prompt,
            "video_path": video_path,
            "image_path": image_paths[0],
            "image_paths": image_paths,
            "inputs": _parse_inputs(inputs),
            "audio_mode": audio_mode,
            "bgm_path": bgm_path.strip() or None,
            "bgm_volume": bgm_volume,
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
    language: Annotated[str, Form()] = "",
    animate: Annotated[bool, Form()] = False,
    animate_prompt: Annotated[str, Form()] = "",
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
    audio_mode: Annotated[str, Form()] = "custom",
    show_subtitle: Annotated[str, Form()] = "true",
    subtitle_size: Annotated[float, Form()] = 0,
    subtitle_color: Annotated[str, Form()] = "",
    tts_provider_id: Annotated[int | None, Form()] = None,
    llm_provider_id: Annotated[int | None, Form()] = None,
    llm_model: Annotated[str, Form()] = "",
    video_provider_id: Annotated[int | None, Form()] = None,
    wait: bool = False,
) -> Job:
    if audio_mode not in {"custom", "auto"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配音模式只能是自定义或模型原声")
    burn_subtitle = _form_bool(show_subtitle, "烧录字幕只能是 true 或 false")
    if subtitle_size < 0 or subtitle_size > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="字幕字号需在 0 到 128 之间")
    subtitle_color = subtitle_color.strip()
    if subtitle_color and not _hex_color(subtitle_color):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="字幕颜色需为 #RRGGBB")
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传至少一个素材")
    if not script and not topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文案或主题")
    media = await _read_media(images)
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
            "language": language,
            "animate": animate,
            "animate_prompt": animate_prompt,
            "video_workflow": video_workflow,
            "video_inputs": _parse_inputs(video_inputs),
            "tts_workflow": tts_workflow,
            "tts_inputs": _parse_inputs(tts_inputs),
            "analysis_image_workflow": analysis_image_workflow,
            "analysis_video_workflow": analysis_video_workflow,
            "analysis_inputs": _parse_inputs(analysis_inputs),
            "bgm_path": (bgm_path or "").strip() or None,
            "bgm_volume": bgm_volume,
            "audio_mode": audio_mode,
            "show_subtitle": burn_subtitle,
            "subtitle_size": subtitle_size,
            "subtitle_color": subtitle_color,
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


async def _read_media(images: list[UploadFile]) -> list[dict]:
    """按扩展名把上传文件存成图片或视频素材。"""
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
    return media


@router.post("/assets/script", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def custom_assets_script(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    images: Annotated[list[UploadFile], File()],
    duration: Annotated[int, Form()] = 30,
    hint: Annotated[str, Form()] = "",
    analysis_image_workflow: Annotated[str, Form()] = "",
    analysis_video_workflow: Annotated[str, Form()] = "",
    analysis_inputs: Annotated[str, Form()] = "{}",
    analysis_provider_id: Annotated[int | None, Form()] = None,
    wait: bool = False,
) -> Job:
    """先看素材再写口播。结果是一段可编辑文本，不合成视频。"""
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传至少一个素材")
    media = await _read_media(images)
    gap = analysis_pack_gaps(media, analysis_image_workflow, analysis_video_workflow)
    if gap:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=gap)
    pick_provider(db, "image", analysis_provider_id)
    pick_llm_with_model(db, None, "")
    job = _submit(
        request,
        db,
        user,
        "video.assets.script",
        {
            "media": media,
            "duration": duration,
            "hint": hint,
            "analysis_image_workflow": analysis_image_workflow or None,
            "analysis_video_workflow": analysis_video_workflow or None,
            "analysis_inputs": _parse_inputs(analysis_inputs),
            "providers": {"analysis": analysis_provider_id},
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

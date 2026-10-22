"""角色库：建档、三视图切分、按槽位取图、生成任务。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import Character, Job, User
from liberastra.providers.base import ProviderError
from liberastra.schemas.character import CharacterOut
from liberastra.schemas.job import JobOut
from liberastra.services.characters import (
    SLOTS,
    apply_split,
    remove_character_files,
    save_character_bytes,
    slot_path,
)
from liberastra.services.preferences import get_pref, get_str_pref
from liberastra.services.providers import pick_provider
from liberastra.storage import resolve, save_upload

router = APIRouter(prefix="/characters", tags=["characters"])

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _owned(db, character_id: int, user: User) -> Character:  # noqa: ANN001
    record = db.get(Character, character_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return record


def _tags(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


async def _read(file: UploadFile | None) -> bytes:
    if file is None or not file.filename:
        return b""
    return await file.read()


@router.get("", response_model=list[CharacterOut])
def list_characters(user: CurrentUser, db: DbSession) -> list[Character]:
    return list(db.scalars(select(Character).where(Character.owner_id == user.id)).all())


@router.post("", response_model=CharacterOut, status_code=status.HTTP_201_CREATED)
async def create_character(
    user: CurrentUser,
    db: DbSession,
    name: Annotated[str, Form(min_length=1, max_length=128)],
    description: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    voice_name: Annotated[str, Form()] = "",
    auto_split: Annotated[bool, Form()] = True,
    portrait: Annotated[UploadFile | None, File()] = None,
    turnaround: Annotated[UploadFile | None, File()] = None,
    front: Annotated[UploadFile | None, File()] = None,
    side: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
) -> Character:
    record = Character(
        name=name.strip(),
        description=description.strip(),
        voice_record_id=voice_record_id,
        voice_name=voice_name.strip() or None,
        tags=_tags(tags),
        owner_id=user.id,
    )
    portrait_bytes = await _read(portrait)
    turnaround_bytes = await _read(turnaround)
    front_bytes = await _read(front)
    side_bytes = await _read(side)
    back_bytes = await _read(back)
    if portrait_bytes:
        record.portrait_path = save_character_bytes(portrait_bytes, _suffix(portrait))
    if front_bytes:
        record.front_path = save_character_bytes(front_bytes, _suffix(front))
    if side_bytes:
        record.side_path = save_character_bytes(side_bytes, _suffix(side))
    if back_bytes:
        record.back_path = save_character_bytes(back_bytes, _suffix(back))
    if turnaround_bytes and auto_split:
        try:
            apply_split(record, turnaround_bytes)
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    elif turnaround_bytes:
        record.turnaround_path = save_character_bytes(turnaround_bytes, _suffix(turnaround))
    if not record.portrait_path and record.front_path:
        record.portrait_path = record.front_path
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/generate", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def generate_character(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    name: Annotated[str, Form(min_length=1, max_length=128)],
    description: Annotated[str, Form()] = "",
    prompt: Annotated[str, Form()] = "",
    provider_id: Annotated[int | None, Form()] = None,
    t2i_workflow: Annotated[str, Form()] = "",
    voice_record_id: Annotated[int | None, Form()] = None,
    ref_images: Annotated[list[UploadFile] | None, File()] = None,
) -> Job:
    saved_provider = provider_id or get_pref(db, "default_character_provider_id") or None
    provider = pick_provider(db, "image", saved_provider)
    saved_workflow = get_str_pref(db, "default_character_workflow").strip()
    workflow = t2i_workflow.strip() or saved_workflow or "qwen_image_21"
    ref_paths: list[str] = []
    for item in ref_images or []:
        content = await item.read()
        if content:
            ref_paths.append(save_upload(item.filename or "ref.png", content))
    if len(ref_paths) > 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参考图最多 3 张")
    if not description.strip() and not prompt.strip() and not ref_paths:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写外观描述或上传参考图")
    record = Character(
        name=name.strip(),
        description=description.strip(),
        voice_record_id=voice_record_id,
        tags=[],
        owner_id=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="character.generate",
        params={
            "character_id": record.id,
            "description": record.description,
            "prompt": prompt.strip() or record.description,
            "t2i_workflow": workflow,
            "ref_image_paths": ref_paths,
        },
        provider_id=provider.id,
    )
    return job


@router.get("/{character_id}/image/{slot}")
def character_image(character_id: int, slot: str, user: CurrentUser, db: DbSession) -> FileResponse:
    if slot not in SLOTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个视角")
    record = _owned(db, character_id, user)
    rel = slot_path(record, slot)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这个视角还没有图片")
    path = resolve(rel)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片文件不存在")
    return FileResponse(path, media_type=_MIME.get(path.suffix.lower(), "application/octet-stream"))


@router.patch("/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: int,
    user: CurrentUser,
    db: DbSession,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
    voice_record_id: Annotated[int | None, Form()] = None,
    voice_name: Annotated[str | None, Form()] = None,
) -> Character:
    record = _owned(db, character_id, user)
    if name is not None and name.strip():
        record.name = name.strip()
    if description is not None:
        record.description = description.strip()
    if tags is not None:
        record.tags = _tags(tags)
    if voice_record_id is not None:
        record.voice_record_id = voice_record_id or None
    if voice_name is not None:
        record.voice_name = voice_name.strip() or None
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _owned(db, character_id, user)
    remove_character_files(record)
    db.delete(record)
    db.commit()


def _suffix(file: UploadFile | None) -> str:
    name = file.filename if file and file.filename else "image.png"
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ".png"

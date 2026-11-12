"""角色库：建档、四视图生成/修改、按槽位取图、下载角色卡。"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.routes._cache import BINARY_CACHE
from liberastra.models import Character, Job, User
from liberastra.providers.base import ProviderError
from liberastra.schemas.asset import AssetOut
from liberastra.schemas.character import CharacterOut
from liberastra.schemas.job import JobOut
from liberastra.services.characters import (
    CHARACTER_VIEW_SLOTS,
    SLOTS,
    apply_grid_split,
    apply_split,
    character_generation_config,
    character_needs_generation,
    ensure_character_asset,
    remove_character_assets,
    remove_character_files,
    save_character_bytes,
    slot_path,
    validate_character_view_image,
)
from liberastra.services.preferences import get_pref
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
    sheet_layout: Annotated[str, Form()] = "wide",
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
    if sheet_layout not in ("wide", "grid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知定妆照排版")
    if turnaround_bytes and auto_split:
        try:
            if sheet_layout == "grid":
                apply_grid_split(record, turnaround_bytes)
            else:
                apply_split(record, turnaround_bytes)
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    elif turnaround_bytes:
        if sheet_layout == "grid":
            record.turnaround_grid_path = save_character_bytes(
                turnaround_bytes, _suffix(turnaround)
            )
        else:
            record.turnaround_path = save_character_bytes(turnaround_bytes, _suffix(turnaround))
    if not record.portrait_path and record.front_path:
        record.portrait_path = record.front_path
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/config")
def character_config(
    user: CurrentUser, db: DbSession, provider_id: int | None = None
) -> dict[str, object]:
    """角色页进入时检查生成配置；缺失时前端显示横幅和系统设置链接。"""
    config = character_generation_config(
        db, provider_id or get_pref(db, "default_character_provider_id") or None
    )
    provider = config.get("provider")
    return {
        "mode": config.get("mode"),
        "missing": config.get("missing") or [],
        "provider_id": getattr(provider, "id", None),
        "provider_name": getattr(provider, "name", None),
        "workflows": config.get("workflows") or {},
        "model": config.get("model") or "",
    }


@router.post("/generate", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def generate_character(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    name: Annotated[str | None, Form(max_length=128)] = None,
    description: Annotated[str, Form()] = "",
    prompt: Annotated[str, Form()] = "",
    character_id: Annotated[int | None, Form()] = None,
    target_view: Annotated[str, Form()] = "",
    order: Annotated[str, Form()] = "face",
    provider_id: Annotated[int | None, Form()] = None,
    voice_record_id: Annotated[int | None, Form()] = None,
    portrait: Annotated[UploadFile | None, File()] = None,
    front: Annotated[UploadFile | None, File()] = None,
    side: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
    ref_image: Annotated[UploadFile | None, File()] = None,
    ref_images: Annotated[list[UploadFile] | None, File()] = None,
    cleared_slots: Annotated[str, Form()] = "",
) -> Job:
    if order not in ("face", "body"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="生成顺序只有 face/body")
    if target_view and target_view not in CHARACTER_VIEW_SLOTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标视角不存在")

    cleared = {
        part.strip()
        for part in cleared_slots.split(",")
        if part.strip() in CHARACTER_VIEW_SLOTS
    }

    uploads: dict[str, tuple[str, bytes]] = {}
    for slot, file in (("portrait", portrait), ("front", front), ("side", side), ("back", back)):
        content = await _read(file)
        if not content:
            continue
        try:
            validate_character_view_image(content, slot)
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        uploads[slot] = (file.filename or f"{slot}.png", content)

    ref_files = [file for file in [ref_image, *(ref_images or [])] if file and file.filename]
    record = _owned(db, character_id, user) if character_id is not None else None
    description_mode = record is None and not uploads and not cleared
    prompt_text = prompt.strip()
    target = target_view.strip()
    if description_mode:
        target = ""
        prompt_text = ""
        name_text = (name or "").strip()
        description_text = description.strip() or prompt.strip()
        if not name_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请填写角色名称"
            )
        if not description_text and not ref_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请填写外观描述或上传参考图"
            )
    else:
        name_text = (name or "").strip() or (record.name if record else "")
        description_text = description.strip() or (record.description if record else "")
        if not name_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请填写角色名称"
            )
        def slot_value(slot: str) -> bytes | str | None:
            if slot in uploads:
                return uploads[slot][1]
            if slot in cleared:
                return None
            return slot_path(record, slot) if record else None

        effective = {slot: slot_value(slot) for slot in CHARACTER_VIEW_SLOTS}
        has_head = bool(effective.get("portrait") or effective.get("front"))
        if not has_head:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要上传面部特写或正面全身",
            )
        if prompt_text:
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="请选择要修改的目标视角"
                )
            if not effective.get(target):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="目标视角还没有图片，无法按提示词修改",
                )

    if description_mode:
        if len(ref_files) > 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="参考图最多 3 张"
            )
    elif len(ref_files) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="补充参考图最多 1 张"
        )
    ref_contents: list[tuple[str, bytes]] = []
    for file in ref_files:
        content = await file.read()
        if content:
            ref_contents.append((file.filename or "ref.png", content))

    chosen_provider_id = provider_id or get_pref(db, "default_character_provider_id") or None
    config = character_generation_config(db, chosen_provider_id)
    available = {
        slot: (
            "upload"
            if slot in uploads
            else (
                None
                if slot in cleared
                else (slot_path(record, slot) if record else None)
            )
        )
        for slot in CHARACTER_VIEW_SLOTS
    }
    needs_generation = description_mode or character_needs_generation(available, prompt_text)
    if needs_generation and config.get("missing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "character_config_missing",
                "missing": config["missing"],
            },
        )
    if not needs_generation:
        config = {
            "provider": None,
            "mode": "compose",
            "workflows": {},
            "model": "",
            "missing": [],
        }

    uploaded_slots = {
        slot: save_upload(filename, content) for slot, (filename, content) in uploads.items()
    }
    ref_paths = [save_upload(filename, content) for filename, content in ref_contents]
    if record is None:
        record = Character(
            name=name_text,
            description=description_text,
            voice_record_id=voice_record_id,
            tags=[],
            owner_id=user.id,
        )
        db.add(record)
    else:
        record.name = name_text
        record.description = description_text
    db.commit()
    db.refresh(record)

    effective_slots = {
        slot: (
            uploaded_slots.get(slot)
            or (None if slot in cleared else slot_path(record, slot))
        )
        for slot in CHARACTER_VIEW_SLOTS
    }
    provider = config.get("provider")
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="character.generate",
        params={
            "character_id": record.id,
            "description": description_text,
            "prompt": prompt_text,
            "target_view": target if prompt_text else "",
            "order": order,
            "slots": effective_slots,
            "uploaded_slots": uploaded_slots,
            "ref_image_path": "" if description_mode else (ref_paths[0] if ref_paths else ""),
            "ref_image_paths": ref_paths if description_mode else [],
            "config": {
                "mode": config.get("mode") or "compose",
                "workflows": config.get("workflows") or {},
                "model": config.get("model") or "",
            },
        },
        provider_id=getattr(provider, "id", None),
    )
    return job


@router.post("/{character_id}/asset/{slot}", response_model=AssetOut)
def register_character_asset(character_id: int, slot: str, user: CurrentUser, db: DbSession) -> AssetOut:
    """把角色某一视角登记成图片资产，供画布按资产引用。重复调用返回同一条。"""
    if slot not in SLOTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视角不存在")
    record = _owned(db, character_id, user)
    try:
        asset = ensure_character_asset(db, record, slot)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AssetOut.model_validate(asset)


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
    return FileResponse(
        path,
        media_type=_MIME.get(path.suffix.lower(), "application/octet-stream"),
        headers=BINARY_CACHE,
    )


@router.get("/{character_id}/download")
def download_character(character_id: int, user: CurrentUser, db: DbSession) -> Response:
    """下载最终六图和 character.json，不含原始上传图与补充参考图。"""
    record = _owned(db, character_id, user)
    entries = (
        ("portrait.png", record.portrait_path),
        ("front.png", record.front_path),
        ("side.png", record.side_path),
        ("back.png", record.back_path),
        ("turnaround_grid.png", record.turnaround_grid_path),
        ("turnaround.png", record.turnaround_path),
    )
    present = [(name, path) for name, path in entries if path and resolve(path).is_file()]
    if not present:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色还没有可下载的图片")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in present:
            archive.write(resolve(path), name)
        archive.writestr(
            "character.json",
            json.dumps(
                {
                    "id": record.id,
                    "name": record.name,
                    "description": record.description,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "files": [name for name, _ in present],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            **BINARY_CACHE,
            "Content-Disposition": f'attachment; filename="character-{record.id}.zip"',
        },
    )


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
    remove_character_assets(db, record)
    remove_character_files(record)
    db.delete(record)
    db.commit()


def _suffix(file: UploadFile | None) -> str:
    name = file.filename if file and file.filename else "image.png"
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ".png"

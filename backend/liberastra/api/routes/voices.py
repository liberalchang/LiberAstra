"""音色库路由：列表、上传参考音频创建、设为默认、删除。"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import User, Voice
from liberastra.schemas.voice import VoiceOut
from liberastra.storage import resolve, save_ref_audio

router = APIRouter(prefix="/voices", tags=["voices"])


def _get_owned(db, voice_id: int, user: User) -> Voice:  # noqa: ANN001
    record = db.get(Voice, voice_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音色不存在")
    return record


@router.get("", response_model=list[VoiceOut])
def list_voices(user: CurrentUser, db: DbSession) -> list[Voice]:
    return list(db.scalars(select(Voice).where(Voice.owner_id == user.id)).all())


@router.post("", response_model=VoiceOut, status_code=status.HTTP_201_CREATED)
async def create_voice(
    user: CurrentUser,
    db: DbSession,
    name: Annotated[str, Form(min_length=1, max_length=128)],
    provider_id: Annotated[int | None, Form()] = None,
    voice_id: Annotated[str | None, Form()] = None,
    ref_text: Annotated[str | None, Form()] = None,
    tags: Annotated[str, Form()] = "",
    file: Annotated[UploadFile | None, File()] = None,
) -> Voice:
    ref_audio_path = None
    if file is not None and file.filename:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
        ref_audio_path = save_ref_audio(file.filename, content)

    record = Voice(
        name=name,
        provider_id=provider_id,
        voice_id=voice_id,
        ref_audio_path=ref_audio_path,
        ref_text=ref_text,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        owner_id=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{voice_id}/default", response_model=VoiceOut)
def set_default_voice(voice_id: int, user: CurrentUser, db: DbSession) -> Voice:
    record = _get_owned(db, voice_id, user)
    db.execute(update(Voice).where(Voice.owner_id == user.id).values(is_default=False))
    record.is_default = True
    db.commit()
    db.refresh(record)
    return record


@router.get("/{voice_id}/ref-audio")
def voice_ref_audio(voice_id: int, user: CurrentUser, db: DbSession) -> FileResponse:
    record = _get_owned(db, voice_id, user)
    if not record.ref_audio_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音色没有参考音频")
    try:
        path = resolve(record.ref_audio_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径") from exc
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="参考音频文件不存在")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    filename = f"{Path(record.name).name or 'voice'}{path.suffix}"
    return FileResponse(path, media_type=media_type, filename=filename)


@router.delete("/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice(voice_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _get_owned(db, voice_id, user)
    if record.ref_audio_path:
        try:
            resolve(record.ref_audio_path).unlink(missing_ok=True)
        except ValueError:
            pass
    db.delete(record)
    db.commit()

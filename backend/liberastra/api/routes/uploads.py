"""通用上传：先存文件拿到相对路径，供后续任务参数（如 BGM）引用。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from liberastra.api.deps import CurrentUser
from liberastra.storage import save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    path: str
    size: int


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload(user: CurrentUser, file: Annotated[UploadFile, File()]) -> UploadOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    return UploadOut(path=save_upload(file.filename or "upload.bin", content), size=len(content))

"""模板路由：分镜模板列表、预览渲染、上传、删除。"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from liberastra.api.deps import CurrentUser
from liberastra.media.htmlframe import render_html
from liberastra.media.thumbs import clear_template_thumbs, template_thumb_path, webp_thumb_bytes
from liberastra.providers.base import ProviderError
from liberastra.services import templates as tpl_service
from liberastra.services.templates import TemplateInfo

router = APIRouter(prefix="/templates", tags=["templates"])

# 预览渲染用的示例占位值（模板里没有的键由模板默认值兜底）
SAMPLE_VALUES = {
    "title": "示例标题",
    "text": "这是一段示例口播文案，用来预览模板的排版效果。",
    "author": "LiberAstra",
    "brand": "LiberAstra",
    "describe": "本机 AIGC 创作台",
}


def _out(t: TemplateInfo) -> dict:
    return {
        "name": t.name,
        "aspect": t.aspect,
        "type": t.type,
        "type_label": t.type_label,
        "source": t.source,
        "width": t.width,
        "height": t.height,
        "media_width": t.media_width,
        "media_height": t.media_height,
        "needs_image": t.needs_image,
        "params": {k: {"type": p.type, "default": p.default} for k, p in t.params.items()},
    }


@router.get("")
def list_templates(
    aspect: str | None = None,
    type: str | None = None,  # noqa: A002
    user: CurrentUser = None,
) -> list[dict]:
    return [_out(t) for t in tpl_service.list_templates(aspect, type)]


@router.get("/{aspect}/{name}/preview")
async def preview_template(aspect: str, name: str, user: CurrentUser) -> Response:
    try:
        tpl = tpl_service.get_template(name, aspect)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    cache = template_thumb_path(aspect, name, tpl.path.stat().st_mtime_ns)
    if cache.exists() and cache.stat().st_size > 0:
        return Response(
            content=cache.read_bytes(),
            media_type="image/webp",
            headers={"Cache-Control": "private, max-age=86400"},
        )
    html = tpl_service.render(tpl, SAMPLE_VALUES)
    try:
        jpeg = await render_html(html, width=tpl.width, height=tpl.height, fmt="jpeg")
        webp = await asyncio.to_thread(webp_thumb_bytes, jpeg)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    await asyncio.to_thread(_store_template_thumb, cache, webp, aspect, name)
    return Response(
        content=webp,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_template(
    user: CurrentUser,
    aspect: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    try:
        saved = tpl_service.save_template(aspect, file.filename or "template.html", await file.read())
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    clear_template_thumbs(aspect, saved.name)
    return _out(saved)


@router.delete("/{aspect}/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(aspect: str, name: str, user: CurrentUser) -> None:
    try:
        tpl_service.delete_template(name, aspect)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    clear_template_thumbs(aspect, name)


def _store_template_thumb(cache, webp: bytes, aspect: str, name: str) -> None:  # noqa: ANN001
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(webp)
    clear_template_thumbs(aspect, name, keep=cache)

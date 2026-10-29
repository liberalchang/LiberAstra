"""云端模型出图 / 出视频。画布节点和功能页共用，不经过 ComfyUI 工作流包。

调用方：canvas_node_job、image.generate / video.i2v 在目标是模型时。
"""

from __future__ import annotations

import base64
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.vendors.volcengine.schemas import data_url
from liberastra.services.providers import build_adapter
from liberastra.storage import resolve

IMAGE_SUBS = {"t2i", "i2i_single", "i2i_multi", "upscale"}
VIDEO_SUBS = {"t2v", "i2v_first", "i2v_flf", "v2v_ref"}


def output_kind(sub_capability: str) -> str:
    if sub_capability in VIDEO_SUBS:
        return "video"
    if sub_capability in IMAGE_SUBS:
        return "image"
    raise ProviderError(f"该模型能力还不能在这里执行: {sub_capability}")


async def generate_model_media(
    provider,  # noqa: ANN001
    *,
    model: str,
    sub_capability: str,
    prompt: str,
    inputs: dict[str, Any] | None = None,
    on_progress: Any = None,
    wait_timeout: float = 900.0,
) -> list[tuple[str, bytes]]:
    if not model:
        raise ProviderError("还没有选择模型")
    values = dict(inputs or {})
    adapter = build_adapter(provider)
    if sub_capability in IMAGE_SUBS:
        images = _image_data_urls(values)
        return await adapter.generate(
            prompt=prompt,
            size=str(values.get("size") or "2K"),
            n=int(values.get("n") or 1),
            model=model,
            images=images,
            output_format=values.get("output_format") or "png",
            watermark=bool(values.get("watermark", False)),
            sequential_image_generation=values.get("sequential_image_generation") or "disabled",
        )
    if sub_capability in VIDEO_SUBS:
        filename, content = await adapter.generate_video(
            model=model,
            prompt=prompt,
            sub_capability=sub_capability,
            images=_slot_urls(values, {"first_frame", "last_frame", "reference_image", "image"}),
            videos=_path_urls(values.get("reference_video") or values.get("video"), "video/mp4"),
            audios=_path_urls(values.get("reference_audio") or values.get("audio"), "audio/mpeg"),
            on_progress=on_progress,
            wait_timeout=wait_timeout,
            resolution=values.get("resolution") or "720p",
            ratio=values.get("ratio") or "16:9",
            duration=int(values.get("duration") or 5),
            generate_audio=bool(values.get("generate_audio", True)),
            camera_fixed=bool(values.get("camera_fixed", False)),
            watermark=bool(values.get("watermark", False)),
            seed=int(values.get("seed") or -1),
        )
        return [(filename, content)]
    raise ProviderError(f"该模型能力还不能在这里执行: {sub_capability}")


def _image_data_urls(values: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ("image", "first_frame", "last_frame", "reference_image"):
        urls.extend(_path_urls(values.get(key), "image/png"))
    return urls


def _slot_urls(values: dict[str, Any], keys: set[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key in keys:
        urls = _path_urls(values.get(key), "image/png")
        if urls:
            grouped[key] = urls
    return grouped


def _path_urls(raw: Any, mime: str) -> list[str]:
    if raw is None or raw == "":
        return []
    paths = raw if isinstance(raw, list) else [raw]
    urls: list[str] = []
    for path in paths:
        text = str(path)
        if text.startswith(("http://", "https://", "data:")):
            urls.append(text)
            continue
        local = resolve(text)
        payload = local.read_bytes()
        if mime.startswith("image/"):
            urls.append(data_url(local.name, payload))
        else:
            encoded = base64.b64encode(payload).decode("ascii")
            urls.append(f"data:{mime};base64,{encoded}")
    return urls

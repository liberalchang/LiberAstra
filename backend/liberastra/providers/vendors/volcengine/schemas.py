"""火山方舟图像 / 视频请求体。纯函数，方便单测，不发网络请求。"""

from __future__ import annotations

import base64
from typing import Any

from liberastra.providers.base import ProviderError

# 动态表单字段，结构与工作流包 manifest inputs 对齐（去掉 node/field）。
IMAGE_FIELDS: dict[str, dict[str, Any]] = {
    "size": {
        "type": "str",
        "label": "尺寸",
        "default": "2K",
        "options": ["2K", "2048x2048", "1920x1080", "1080x1920", "1024x1024"],
    },
    "output_format": {
        "type": "str",
        "label": "格式",
        "default": "png",
        "options": ["png", "jpeg"],
    },
    "watermark": {"type": "bool", "label": "水印", "default": False},
}

VIDEO_FIELDS: dict[str, dict[str, Any]] = {
    "resolution": {
        "type": "str",
        "label": "分辨率",
        "default": "720p",
        "options": ["480p", "720p", "1080p"],
    },
    "ratio": {
        "type": "str",
        "label": "画幅",
        "default": "16:9",
        "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
    },
    "duration": {"type": "int", "label": "时长（秒）", "default": 5, "min": -1, "max": 30},
    "generate_audio": {"type": "bool", "label": "生成音频", "default": True},
    "camera_fixed": {"type": "bool", "label": "固定镜头", "default": False},
    "watermark": {"type": "bool", "label": "水印", "default": False},
    "seed": {"type": "int", "label": "种子", "default": -1, "min": -1, "max": 2147483647},
}


def apply_saved_defaults(
    fields: dict[str, dict[str, Any]],
    defaults: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """把模型上保存的默认值写进表单。键必须是这个能力本来就有的字段。"""
    if not defaults:
        return fields
    merged: dict[str, dict[str, Any]] = {}
    for key, spec in fields.items():
        if key not in defaults:
            merged[key] = spec
            continue
        merged[key] = {**spec, "default": defaults[key]}
    return merged


def fields_for(sub_capability: str) -> dict[str, dict[str, Any]]:
    if sub_capability in {"t2i", "i2i_single", "i2i_multi"}:
        fields = dict(IMAGE_FIELDS)
        if sub_capability == "t2i":
            fields["sequential_image_generation"] = {
                "type": "str",
                "label": "组图",
                "default": "disabled",
                "options": ["disabled", "auto"],
            }
        return fields
    if sub_capability in {"t2v", "i2v_first", "i2v_flf", "v2v_ref"}:
        return dict(VIDEO_FIELDS)
    return {}


def data_url(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "gif": "gif"}.get(ext, "png")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def image_body(
    *,
    model: str,
    prompt: str,
    size: str = "2K",
    output_format: str = "png",
    watermark: bool = False,
    images: list[str] | None = None,
    sequential: str = "disabled",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "output_format": output_format,
        "watermark": watermark,
        "response_format": "url",
        "sequential_image_generation": sequential if sequential in {"auto", "disabled"} else "disabled",
    }
    if images:
        body["image"] = images[0] if len(images) == 1 else images
    return body


def _needs_adaptive_ratio(model: str, sub_capability: str) -> bool:
    """Seedance 2.5 首尾帧只接受 adaptive 画幅。"""
    lowered = model.lower()
    return sub_capability == "i2v_flf" and "seedance-2-5" in lowered


def video_body(
    *,
    model: str,
    prompt: str,
    sub_capability: str,
    images: dict[str, list[str]] | None = None,
    videos: list[str] | None = None,
    audios: list[str] | None = None,
    resolution: str = "720p",
    ratio: str = "16:9",
    duration: int = 5,
    generate_audio: bool = True,
    camera_fixed: bool = False,
    watermark: bool = False,
    seed: int = -1,
) -> dict[str, Any]:
    """按火山互斥规则组装 content。首尾帧与参考素材不能出现在同一次请求里。"""
    content: list[dict[str, Any]] = []
    if prompt.strip():
        content.append({"type": "text", "text": prompt.strip()})
    images = images or {}
    if sub_capability == "i2v_first":
        frame = _first(images.get("first_frame") or images.get("image"))
        if not frame:
            raise ProviderError("首帧生视频需要一张首帧图片")
        content.append(_image_part(frame, "first_frame"))
    elif sub_capability == "i2v_flf":
        first = _first(images.get("first_frame") or images.get("image"))
        last = _first(images.get("last_frame"))
        if not first or not last:
            raise ProviderError("首尾帧生视频需要首帧和尾帧两张图片")
        content.append(_image_part(first, "first_frame"))
        content.append(_image_part(last, "last_frame"))
    elif sub_capability == "v2v_ref":
        for url in images.get("reference_image") or images.get("image") or []:
            content.append(_image_part(url, "reference_image"))
        for url in videos or []:
            content.append(
                {"type": "video_url", "video_url": {"url": url}, "role": "reference_video"}
            )
        for url in audios or []:
            content.append(
                {"type": "audio_url", "audio_url": {"url": url}, "role": "reference_audio"}
            )
    elif sub_capability != "t2v":
        raise ProviderError(f"火山方舟暂不支持该视频能力: {sub_capability}")
    if not content:
        raise ProviderError("视频请求缺少提示词或参考素材")
    if _needs_adaptive_ratio(model, sub_capability):
        ratio = "adaptive"
    body: dict[str, Any] = {
        "model": model,
        "content": content,
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": generate_audio,
        "camera_fixed": camera_fixed,
        "watermark": watermark,
    }
    if seed >= 0:
        body["seed"] = seed
    return body


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return str(values[0] or "")


def _image_part(url: str, role: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": url}, "role": role}

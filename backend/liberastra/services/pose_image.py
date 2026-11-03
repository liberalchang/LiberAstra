"""姿势控制图预处理：线稿自动裁白边，深度图保持原样。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from liberastra.providers.base import ProviderError

_WHITE = 240
_DARK = 180
_PADDING = 0.04
_ALREADY_TIGHT = 0.96
_MIN_SIDE = 64


def _flatten(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _has_white_border(image: Image.Image) -> bool:
    gray = image.convert("L")
    width, height = gray.size
    step_x = max(1, width // 64)
    step_y = max(1, height // 64)
    pixels = gray.load()
    samples = (
        [pixels[x, 0] for x in range(0, width, step_x)]
        + [pixels[x, height - 1] for x in range(0, width, step_x)]
        + [pixels[0, y] for y in range(0, height, step_y)]
        + [pixels[width - 1, y] for y in range(0, height, step_y)]
    )
    return bool(samples) and sum(value >= _WHITE for value in samples) / len(samples) >= 0.9


def _content_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    gray = image.convert("L")
    mask = gray.point(lambda value: 255 if value < _DARK else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    if width >= image.width * _ALREADY_TIGHT and height >= image.height * _ALREADY_TIGHT:
        return None
    pad_x = int(width * _PADDING)
    pad_y = int(height * _PADDING)
    box = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )
    if box[2] - box[0] < _MIN_SIDE or box[3] - box[1] < _MIN_SIDE:
        return None
    return box


def prepare_pose_control(content: bytes, filename: str) -> tuple[bytes, str]:
    """线稿/白底姿势图裁到内容边界；深度图或其他整幅图原样返回。"""
    try:
        with Image.open(BytesIO(content)) as opened:
            image = _flatten(opened)
    except (UnidentifiedImageError, OSError) as exc:
        raise ProviderError(f"姿势参考图无法解析: {filename}") from exc

    if not _has_white_border(image):
        return content, filename
    box = _content_box(image)
    if box is None:
        return content, filename

    output = BytesIO()
    image.crop(box).save(output, format="PNG")
    return output.getvalue(), f"{Path(filename).stem}_pose.png"

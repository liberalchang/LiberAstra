"""姿势控制图预处理：透明底压白，保持原始画幅。"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from liberastra.providers.base import ProviderError


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def _flatten(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def prepare_pose_control(content: bytes, filename: str) -> tuple[bytes, str]:
    """透明底压到白底；其他图片原样返回。所有图片都保持原始画幅，不裁剪。"""
    try:
        with Image.open(BytesIO(content)) as opened:
            if not _has_alpha(opened):
                return content, filename
            image = _flatten(opened)
    except (UnidentifiedImageError, OSError) as exc:
        raise ProviderError(f"姿势参考图无法解析: {filename}") from exc

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), filename

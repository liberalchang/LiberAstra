"""姿势控制图预处理：线稿裁白边、深度图保持原样。"""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from liberastra.providers.base import ProviderError
from liberastra.services.pose_image import prepare_pose_control


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _content_bbox(image: Image.Image, threshold: int = 180) -> tuple[int, int, int, int]:
    mask = image.convert("L").point(lambda value: 255 if value < threshold else 0)
    bbox = mask.getbbox()
    assert bbox is not None
    return bbox


def test_lineart_white_margins_are_cropped() -> None:
    image = Image.new("RGB", (400, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([120, 60, 280, 540], outline="black", width=4)
    draw.line([200, 60, 200, 540], fill="black", width=3)

    data, name = prepare_pose_control(_png(image), "lineart.png")

    cropped = Image.open(BytesIO(data))
    assert cropped.mode == "RGB"
    assert cropped.width < 300
    assert cropped.height < 560
    left, top, right, bottom = _content_bbox(cropped)
    assert left <= 20 and top <= 20
    assert cropped.width - right <= 20
    assert cropped.height - bottom <= 20
    assert name == "lineart_pose.png"


def test_depth_image_is_left_untouched() -> None:
    image = Image.new("RGB", (300, 400), (18, 18, 18))
    draw = ImageDraw.Draw(image)
    draw.ellipse([100, 80, 200, 320], fill=(220, 220, 220))
    raw = _png(image)

    data, name = prepare_pose_control(raw, "depth.png")

    assert data == raw
    assert name == "depth.png"


def test_transparent_lineart_is_flattened_and_cropped() -> None:
    image = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle([80, 40, 220, 360], outline=(0, 0, 0, 255), width=4)

    data, name = prepare_pose_control(_png(image), "alpha.png")

    cropped = Image.open(BytesIO(data))
    assert cropped.mode == "RGB"
    assert cropped.width < 300
    assert cropped.height < 400
    assert name == "alpha_pose.png"


def test_tight_lineart_is_not_reencoded() -> None:
    image = Image.new("RGB", (200, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([2, 2, 197, 297], outline="black", width=2)
    raw = _png(image)

    data, name = prepare_pose_control(raw, "tight.png")

    assert data == raw
    assert name == "tight.png"


def test_invalid_image_raises_provider_error() -> None:
    with pytest.raises(ProviderError, match="姿势参考图"):
        prepare_pose_control(b"not an image", "broken.png")

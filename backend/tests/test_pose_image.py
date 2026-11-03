"""姿势控制图预处理：保持原始画幅，透明底压白。"""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from liberastra.providers.base import ProviderError
from liberastra.services.pose_image import prepare_pose_control


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_lineart_white_margins_are_preserved() -> None:
    image = Image.new("RGB", (400, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([120, 60, 280, 540], outline="black", width=4)
    draw.line([200, 60, 200, 540], fill="black", width=3)
    raw = _png(image)

    data, name = prepare_pose_control(raw, "lineart.png")

    assert data == raw
    assert name == "lineart.png"
    assert Image.open(BytesIO(data)).size == image.size


def test_depth_image_is_left_untouched() -> None:
    image = Image.new("RGB", (300, 400), (18, 18, 18))
    draw = ImageDraw.Draw(image)
    draw.ellipse([100, 80, 200, 320], fill=(220, 220, 220))
    raw = _png(image)

    data, name = prepare_pose_control(raw, "depth.png")

    assert data == raw
    assert name == "depth.png"


def test_transparent_lineart_is_flattened_without_cropping() -> None:
    image = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle([80, 40, 220, 360], outline=(0, 0, 0, 255), width=4)

    data, name = prepare_pose_control(_png(image), "alpha.png")

    flattened = Image.open(BytesIO(data))
    assert flattened.mode == "RGB"
    assert flattened.size == image.size
    assert flattened.getpixel((0, 0)) == (255, 255, 255)
    assert name == "alpha.png"


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

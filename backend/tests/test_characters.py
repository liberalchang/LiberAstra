"""角色库：三视图切分，以及上传后能按正/侧/背取出单人图。"""

import io

from fastapi.testclient import TestClient
from PIL import Image

from liberastra.models import Character
from liberastra.services.characters import clean_appearance, paths_for_task, sheet_prompt, split_turnaround


def _sheet() -> bytes:
    image = Image.new("RGB", (400, 80), "white")
    blocks = (
        ((10, 10, 70, 70), (200, 40, 40)),
        ((110, 10, 170, 70), (40, 160, 40)),
        ((210, 10, 270, 70), (40, 40, 200)),
        ((320, 10, 390, 70), (180, 140, 40)),
    )
    for box, color in blocks:
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                image.putpixel((x, y), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _colors(content: bytes) -> set[tuple[int, int, int]]:
    image = Image.open(io.BytesIO(content)).convert("RGB")
    pixels = image.load()
    width, height = image.size
    found: set[tuple[int, int, int]] = set()
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            if pixel != (255, 255, 255):
                found.add(pixel)
    return found


def test_split_turnaround_finds_four_panels() -> None:
    front, side, back, portrait = split_turnaround(_sheet())
    assert _colors(front) == {(200, 40, 40)}
    assert _colors(side) == {(40, 160, 40)}
    assert _colors(back) == {(40, 40, 200)}
    assert _colors(portrait) == {(180, 140, 40)}


def test_split_turnaround_follows_gaps_not_fixed_ratio() -> None:
    """人物不在 23/45/68 上，渐变背景也不能靠左上角色素认缝。"""
    width, height = 600, 120
    image = Image.new("RGB", (width, height))
    for x in range(width):
        tone = int(180 + 60 * x / width)
        for y in range(height):
            image.putpixel((x, y), (tone, tone, tone + 8 if tone < 248 else 255))
    people = (
        (70, 150, (180, 40, 40), (40, 40, 40)),
        (230, 310, (40, 150, 40), (20, 60, 20)),
        (390, 470, (40, 40, 170), (20, 20, 50)),
        (510, 580, (190, 140, 40), (90, 50, 20)),
    )
    for left, right, upper, lower in people:
        for x in range(left, right):
            for y in range(height):
                image.putpixel((x, y), upper if y < height // 2 else lower)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    parts = split_turnaround(buffer.getvalue())
    owned = [_colors(part) for part in parts]
    for index, (_, _, upper, lower) in enumerate(people):
        assert upper in owned[index]
        assert lower in owned[index]
        assert all(upper not in other for other_index, other in enumerate(owned) if other_index != index)


def test_split_portrait_drops_previous_background() -> None:
    """特写换成蓝底时，左缘落在蓝底上，不带前面全身图的灰边。"""
    width, height = 640, 160
    image = Image.new("RGB", (width, height), (200, 202, 206))
    for x in range(470, width):
        for y in range(height):
            image.putpixel((x, y), (40, 58, 88))
    people = (
        (40, 100, (180, 40, 40), (40, 40, 40)),
        (160, 220, (40, 150, 40), (20, 60, 20)),
        (280, 350, (40, 40, 170), (20, 20, 50)),
        (510, 590, (190, 140, 40), (90, 50, 20)),
    )
    for left, right, upper, lower in people:
        for x in range(left, right):
            for y in range(24, height):
                image.putpixel((x, y), upper if y < height // 2 else lower)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    front, side, back, portrait = split_turnaround(buffer.getvalue())
    panel = Image.open(io.BytesIO(portrait)).convert("RGB")
    assert panel.load()[2, 8] == (40, 58, 88)
    assert (190, 140, 40) in _colors(portrait)
    assert (40, 40, 170) not in _colors(portrait)
    assert (180, 40, 40) in _colors(front)
    assert (40, 150, 40) in _colors(side)
    assert (40, 40, 170) in _colors(back)


def test_clean_appearance_drops_sheet_layout() -> None:
    text = (
        "现代清冷甜美系年轻女生角色三视图设定，20岁左右，冷白皮。"
        "16:9横版角色设定图，画面依次展示完整全身正面。"
        "段与段之间留出空白间隔。"
        "写实真人质感，8K超高清。"
    )
    cleaned = clean_appearance(text)
    assert "20岁左右" in cleaned
    assert "16:9" not in cleaned
    assert "空白间隔" not in cleaned
    assert "三视图设定" not in cleaned
    expanded = sheet_prompt("20岁，黑长发")
    assert "完整全身正面" in expanded
    assert sheet_prompt(expanded) == expanded


def test_create_character_splits_turnaround(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "林梦影", "description": "黑长直，白衬衫", "auto_split": "true"},
        files={"turnaround": ("sheet.png", _sheet(), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["front_path"]
    assert body["side_path"]
    assert body["back_path"]
    assert body["portrait_path"]
    assert body["portrait_path"] != body["front_path"]
    character = Character(
        name=body["name"],
        description=body["description"],
        portrait_path=body["portrait_path"],
        front_path=body["front_path"],
        side_path=body["side_path"],
        back_path=body["back_path"],
        owner_id=1,
    )
    assert len(paths_for_task(character, "front", multi=True)) == 3
    assert paths_for_task(character, "portrait", multi=False) == [body["portrait_path"]]
    image = client.get(f"/api/v1/characters/{body['id']}/image/front", headers=auth_header)
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")

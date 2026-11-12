"""角色库：四段式/四宫格切分、排版提示词和生成任务。"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from liberastra.models import Character
from liberastra.providers.base import ProviderError
from liberastra.services.characters import (
    build_wide_sheet_reference,
    clean_appearance,
    expand_reference_paths,
    paths_for_task,
    prepare_character_ref_images,
    reference_paths,
    reference_views,
    sheet_prompt,
    split_turnaround,
    split_turnaround_grid,
)
from liberastra.storage import resolve


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


def _solid(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _grid_sheet() -> bytes:
    width, height = 576, 1024
    image = Image.new("RGB", (width, height), "white")
    image.paste((200, 40, 40), (0, 0, width // 2, height // 2))
    image.paste((40, 160, 40), (width // 2, 0, width, height // 2))
    image.paste((40, 40, 200), (0, height // 2, width // 2, height))
    image.paste((180, 140, 40), (width // 2, height // 2, width, height))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_split_turnaround_grid_returns_four_9x16() -> None:
    normalized, portrait, front, side, back = split_turnaround_grid(_grid_sheet())
    assert Image.open(io.BytesIO(normalized)).size == (576, 1024)
    for color, part in (
        ((200, 40, 40), portrait),
        ((40, 160, 40), front),
        ((40, 40, 200), side),
        ((180, 140, 40), back),
    ):
        panel = Image.open(io.BytesIO(part))
        assert panel.size == (288, 512)
        assert panel.size[0] * 16 == panel.size[1] * 9
        assert _colors(part) == {color}


def test_split_turnaround_grid_rejects_non_9x16() -> None:
    with pytest.raises(ProviderError):
        split_turnaround_grid(_solid(400, 400, (1, 2, 3)))


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
    anchored = sheet_prompt("", references=1)
    assert anchored.startswith("保持参考图")
    assert "完整全身正面" in anchored


def test_sheet_prompt_does_not_force_expression() -> None:
    prompt = sheet_prompt("20岁，黑长发，闭眼，冷峻表情")
    assert "闭眼" in prompt
    assert "冷峻表情" in prompt
    assert "眨眼" not in prompt
    assert "俏皮" not in prompt


def test_sheet_prompt_keeps_layout_for_aspect_only() -> None:
    """用户只写 16:9 电影感，不等于已经写了四段式排版。"""
    prompt = sheet_prompt("20岁，黑长发，16:9 电影感")
    assert "16:9" in prompt
    assert "完整全身正面" in prompt
    assert "右侧超大面部" in prompt
    assert "眨眼" not in prompt
    assert "俏皮" not in prompt


def test_sheet_prompt_builds_grid_layout_and_cleans_it() -> None:
    prompt = sheet_prompt("20岁，黑长发", layout="grid")
    for marker in ("9:16", "2×2", "四宫格", "左上", "右上", "左下", "右下", "正面面部"):
        assert marker in prompt
    assert "16:9横版" not in prompt
    cleaned = clean_appearance(prompt)
    assert "20岁" in cleaned
    assert "四宫格" not in cleaned
    assert "9:16" not in cleaned
    assert sheet_prompt(prompt, layout="grid") == prompt

    wide = sheet_prompt("20岁，黑长发")
    switched = sheet_prompt(wide, layout="grid")
    assert "四宫格" in switched
    assert "16:9横版" not in switched


def test_prepare_character_ref_images_uses_target_aspect() -> None:
    raw = _solid(400, 300, (10, 20, 30))
    prepared = prepare_character_ref_images([raw], target=(1152, 2048))
    image = Image.open(io.BytesIO(prepared[0]))
    assert image.size == (1152, 2048)
    assert image.getpixel((0, 0)) == (230, 230, 230)
    pair = prepare_character_ref_images([raw, raw], target=(1152, 2048))
    assert Image.open(io.BytesIO(pair[1])).size == (400, 300)


def test_build_wide_sheet_reference_places_four_views() -> None:
    parts = {
        "front": _solid(90, 160, (200, 40, 40)),
        "side": _solid(90, 160, (40, 160, 40)),
        "back": _solid(90, 160, (40, 40, 200)),
        "portrait": _solid(90, 160, (180, 140, 40)),
    }
    image = Image.open(io.BytesIO(build_wide_sheet_reference(parts)))
    assert image.size == (1920, 1080)
    assert [image.getpixel((480 * index + 240, 540)) for index in range(4)] == [
        (200, 40, 40),
        (40, 160, 40),
        (40, 40, 200),
        (180, 140, 40),
    ]


def test_character_sheet_task_does_not_force_expression() -> None:
    from liberastra.services.prompts import build_system_prompt

    text = build_system_prompt("character_sheet", user_prompt="20岁，黑长发，闭眼")
    assert "眨眼" not in text
    assert "俏皮" not in text
    assert "用户未指定时" in text
    assert "16:9" not in text


def test_reference_views_follow_slot_count() -> None:
    assert reference_views("i2v", 1, "side") == ["side"]
    assert reference_views("motion", 3, "portrait") == ["front", "side", "back"]
    assert reference_views("i2v", 3, "portrait") == ["portrait", "front", "side"]
    assert reference_views("i2v", 3, "back") == ["back", "front", "side"]
    assert reference_views("avatar", 2, "front") == ["portrait"]
    assert "turnaround" not in reference_views("i2v", 4, "front")
    assert reference_views("i2v", 3, "turnaround") == ["turnaround"]
    assert reference_views("motion", 3, "turnaround") == ["turnaround"]
    assert reference_views("i2v", 1, "turnaround_grid") == ["turnaround_grid"]
    assert reference_views("motion", 3, "turnaround_grid") == ["turnaround_grid"]


def test_reference_paths_skip_missing_and_sheet() -> None:
    from types import SimpleNamespace

    character = SimpleNamespace(
        portrait_path="p.png",
        front_path="f.png",
        side_path=None,
        back_path="b.png",
        turnaround_path="sheet.png",
        turnaround_grid_path="grid.png",
    )
    assert reference_paths(character, "motion", 3, "front") == ["f.png", "b.png"]
    assert reference_paths(character, "i2v", 1, "turnaround") == ["sheet.png"]
    assert reference_paths(character, "i2v", 1, "turnaround_grid") == ["grid.png"]
    assert paths_for_task(character, "turnaround", multi=False) == ["sheet.png"]
    assert paths_for_task(character, "turnaround_grid", multi=False) == ["grid.png"]
    # 侧面缺失时，单槽只要这一张，没有可回退的其他视角。
    try:
        reference_paths(character, "i2v", 1, "side")
        raised = False
    except Exception:
        raised = True
    assert raised
    first = {"portrait": "p.png", "front": "f.png", "side": "s.png", "back": "b.png"}
    second = {"portrait": "p2.png", "front": "f2.png", "side": "s2.png", "back": "b2.png"}
    multi = expand_reference_paths(
        "i2v",
        3,
        [
            {"type": "character", "primary": "portrait", "paths": first},
            {"type": "character", "primary": "back", "paths": second},
        ],
    )
    assert multi == ["p.png", "b2.png"]
    filled = expand_reference_paths(
        "motion",
        3,
        [{"type": "character", "primary": "portrait", "paths": first}],
    )
    assert filled == ["f.png", "s.png", "b.png"]
    assert "p.png" not in filled
    sheet_only = expand_reference_paths(
        "i2v",
        3,
        [{"type": "character", "primary": "turnaround", "paths": {**first, "turnaround": "sheet.png"}}],
    )
    assert sheet_only == ["sheet.png"]


def test_upload_grid_sheet_splits_four_9x16(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "四宫格角色", "description": "", "auto_split": "true", "sheet_layout": "grid"},
        files={"turnaround": ("grid.png", _grid_sheet(), "image/png")},
    )
    assert created.status_code == 201, created.text
    character = created.json()
    assert character["turnaround_grid_path"]
    assert character["turnaround_path"] is None
    for slot, color in (
        ("portrait", (200, 40, 40)),
        ("front", (40, 160, 40)),
        ("side", (40, 40, 200)),
        ("back", (180, 140, 40)),
    ):
        assert character[f"{slot}_path"]
        response = client.get(
            f"/api/v1/characters/{character['id']}/image/{slot}", headers=auth_header
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-cache"
        panel = Image.open(io.BytesIO(response.content)).convert("RGB")
        assert panel.size == (288, 512)
        assert panel.getpixel((144, 256)) == color

    grid = client.get(
        f"/api/v1/characters/{character['id']}/image/turnaround_grid", headers=auth_header
    )
    assert grid.status_code == 200
    assert grid.headers["cache-control"] == "private, no-cache"
    assert Image.open(io.BytesIO(grid.content)).size == (576, 1024)


def test_character_asset_is_idempotent(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "林梦影", "description": "黑长直，白衬衫", "auto_split": "true"},
        files={"turnaround": ("sheet.png", _sheet(), "image/png")},
    )
    assert created.status_code == 201, created.text
    character_id = created.json()["id"]
    first = client.post(f"/api/v1/characters/{character_id}/asset/front", headers=auth_header)
    second = client.post(f"/api/v1/characters/{character_id}/asset/front", headers=auth_header)
    assert first.status_code == 200, first.text
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["origin"] == "character"
    assert first.json()["meta"]["character_slot"] == "front"
    sheet = client.post(f"/api/v1/characters/{character_id}/asset/turnaround", headers=auth_header)
    again = client.post(f"/api/v1/characters/{character_id}/asset/turnaround", headers=auth_header)
    assert sheet.status_code == 200, sheet.text
    assert again.status_code == 200
    assert sheet.json()["id"] == again.json()["id"]
    assert sheet.json()["meta"]["character_slot"] == "turnaround"
    missing = client.post(f"/api/v1/characters/{character_id}/asset/nope", headers=auth_header)
    assert missing.status_code == 400


def test_character_assets_removed_with_character(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    created = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "待删除角色", "description": "黑长直", "auto_split": "true"},
        files={"turnaround": ("sheet.png", _sheet(), "image/png")},
    )
    assert created.status_code == 201, created.text
    character_id = created.json()["id"]

    front = client.post(f"/api/v1/characters/{character_id}/asset/front", headers=auth_header)
    sheet = client.post(
        f"/api/v1/characters/{character_id}/asset/turnaround", headers=auth_header
    )
    assert front.status_code == 200, front.text
    assert sheet.status_code == 200, sheet.text
    asset_ids = [front.json()["id"], sheet.json()["id"]]
    asset_paths = [resolve(front.json()["path"]), resolve(sheet.json()["path"])]
    assert all(path.is_file() for path in asset_paths)

    other = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "保留角色", "description": "短发", "auto_split": "true"},
        files={"turnaround": ("sheet.png", _sheet(), "image/png")},
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    other_front = client.post(f"/api/v1/characters/{other_id}/asset/front", headers=auth_header)
    assert other_front.status_code == 200, other_front.text
    other_asset_id = other_front.json()["id"]
    other_path = resolve(other_front.json()["path"])

    deleted = client.delete(f"/api/v1/characters/{character_id}", headers=auth_header)
    assert deleted.status_code == 204, deleted.text

    for asset_id in asset_ids:
        assert (
            client.get(f"/api/v1/assets/{asset_id}", headers=auth_header).status_code == 404
        )
    assert not any(path.exists() for path in asset_paths)
    assert (
        client.get(f"/api/v1/assets/{other_asset_id}", headers=auth_header).status_code == 200
    )
    assert other_path.is_file()


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

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


def test_split_turnaround_finds_four_panels() -> None:
    front, side, back, portrait = split_turnaround(_sheet())
    assert Image.open(io.BytesIO(front)).size[0] < 150
    assert Image.open(io.BytesIO(side)).size[0] < 150
    assert Image.open(io.BytesIO(back)).size[0] < 150
    assert Image.open(io.BytesIO(portrait)).size[0] < 150


def test_clean_appearance_drops_sheet_layout() -> None:
    text = (
        "现代清冷甜美系年轻女生角色三视图设定，20岁左右，冷白皮。"
        "16:9横版角色设定图，画面依次展示完整全身正面。"
        "写实真人质感，8K超高清。"
    )
    cleaned = clean_appearance(text)
    assert "20岁左右" in cleaned
    assert "16:9" not in cleaned
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

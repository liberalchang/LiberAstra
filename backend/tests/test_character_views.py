"""角色四视图：单张生成顺序、参考图角色、程序合成与单视角修改。"""

from __future__ import annotations

import asyncio
import io
import zipfile
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Character, Job, Provider, User
from liberastra.providers.base import ProviderError
from liberastra.services import characters as characters_service
from liberastra.services.characters import (
    character_generation_config,
    character_needs_generation,
    compose_character_grid,
    run_character_generate_job,
    save_character_bytes,
    validate_character_view_image,
    view_prompt,
)
from liberastra.services.preferences import set_str_pref
from liberastra.storage import resolve

RED = (210, 30, 30)
GREEN = (30, 170, 60)
BLUE = (40, 60, 210)
YELLOW = (220, 190, 40)
MAGENTA = (180, 30, 170)
MODIFIED = (20, 200, 210)


def _solid(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _slot_color(content: bytes) -> tuple[int, int, int]:
    image = Image.open(io.BytesIO(content)).convert("RGB")
    return image.getpixel((4, 4))


def _job(db, owner_id: int, character_id: int, **overrides) -> Job:
    params = {
        "character_id": character_id,
        "description": "20岁，黑长直，白衬衫",
        "prompt": "",
        "target_view": "",
        "order": "face",
        "slots": {},
        "ref_image_path": "",
        "config": {
            "mode": "workflow",
            "workflows": {
                "t2i": "qwen_image_21",
                "single": "qwen_image_21_edit",
                "multi": "qwen_image_21_edit_multi",
            },
            "model": "",
        },
    }
    params.update(overrides)
    job = Job(kind="character.generate", params=params, owner_id=owner_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _fake_slot_color(prompt: str) -> tuple[int, int, int]:
    if "外套" in prompt or "修改" in prompt:
        return MODIFIED
    if "面部特写" in prompt:
        return RED
    if "正面全身" in prompt:
        return GREEN
    if "侧面全身" in prompt:
        return BLUE
    if "背面全身" in prompt:
        return YELLOW
    return (90, 90, 90)


def test_validate_view_requires_9x16_and_min_short_edge() -> None:
    assert validate_character_view_image(_solid(720, 1280, RED), "front") == (720, 1280)
    # 1% 内的近似 9:16 可以接受
    assert validate_character_view_image(_solid(721, 1280, RED), "front") == (721, 1280)
    with pytest.raises(ProviderError):
        validate_character_view_image(_solid(800, 1280, RED), "front")
    with pytest.raises(ProviderError):
        validate_character_view_image(_solid(600, 1067, RED), "front")
    with pytest.raises(ProviderError):
        validate_character_view_image(b"not an image", "front")


def test_character_needs_generation() -> None:
    full = {slot: "x.png" for slot in ("portrait", "front", "side", "back")}
    assert character_needs_generation(full, "") is False
    assert character_needs_generation(full, "把外套改成红色") is True
    assert character_needs_generation({**full, "side": None}, "") is True


def test_compose_grid_places_four_views() -> None:
    grid = compose_character_grid(
        {
            "portrait": _solid(720, 1280, RED),
            "front": _solid(720, 1280, GREEN),
            "side": _solid(720, 1280, BLUE),
            "back": _solid(720, 1280, YELLOW),
        }
    )
    image = Image.open(io.BytesIO(grid)).convert("RGB")
    assert image.size == (1152, 2048)
    assert image.getpixel((288, 512)) == RED
    assert image.getpixel((864, 512)) == GREEN
    assert image.getpixel((288, 1536)) == BLUE
    assert image.getpixel((864, 1536)) == YELLOW


def test_view_prompt_has_single_view_and_no_grid_layout() -> None:
    prompt = view_prompt("20岁，黑长直，白衬衫", "portrait", references=1)
    assert "20岁" in prompt
    assert "面部特写" in prompt
    assert "9:16" in prompt
    assert "四宫格" not in prompt
    front = view_prompt("20岁，黑长直", "front")
    assert "正面全身" in front
    assert "完整全身" in front


def _create_provider(db, *, type_: str, name: str) -> Provider:
    admin = db.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    record = Provider(
        name=name,
        type=type_,
        base_url="http://127.0.0.1:8188",
        models=[],
        capabilities=["image"],
        enabled=True,
        extra={},
        owner_id=admin.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _created_provider_ids.append(record.id)
    return record


_created_provider_ids: list[int] = []


@pytest.fixture(autouse=True)
def _disable_test_providers():
    _created_provider_ids.clear()
    yield
    if not _created_provider_ids:
        return
    with SessionLocal() as db:
        for provider_id in _created_provider_ids:
            record = db.get(Provider, provider_id)
            if record is not None:
                record.enabled = False
        db.commit()


def test_generation_config_checks_three_workflows(client, auth_header) -> None:
    with SessionLocal() as db:
        provider = _create_provider(db, type_="comfyui", name="角色配置测试 Comfy")
        for key in (
            "default_character_workflow",
            "default_character_i2i_workflow",
            "default_character_i2i_multi_workflow",
        ):
            set_str_pref(db, key, "")
        config = character_generation_config(db, provider.id)
        assert len(config["missing"]) == 3
        set_str_pref(db, "default_character_workflow", "qwen_image_21")
        set_str_pref(db, "default_character_i2i_workflow", "qwen_image_21_edit")
        set_str_pref(db, "default_character_i2i_multi_workflow", "qwen_image_21_edit_multi")
        config = character_generation_config(db, provider.id)
        assert config["missing"] == []
        assert config["workflows"]["multi"] == "qwen_image_21_edit_multi"


def test_generation_config_checks_cloud_model(client, auth_header) -> None:
    with SessionLocal() as db:
        provider = _create_provider(db, type_="openai_images", name="角色配置测试云端")
        set_str_pref(db, "default_character_model", "")
        config = character_generation_config(db, provider.id)
        assert config["missing"] == ["角色生图模型"]
        set_str_pref(db, "default_character_model", "gpt-image-1")
        config = character_generation_config(db, provider.id)
        assert config["missing"] == []
        assert config["mode"] == "model"


def _run(db, monkeypatch: pytest.MonkeyPatch, job: Job, fake_produce):
    monkeypatch.setattr(characters_service, "produce_images", fake_produce)
    monkeypatch.setattr(
        characters_service,
        "pick_provider",
        lambda *args, **kwargs: SimpleNamespace(type="comfyui", name="fake", id=1),
    )
    return asyncio.run(run_character_generate_job(db, job, JobContext(JobManager(), job.id)))


def _character(db, *, color_paths: bool = False, name: str = "四视图角色") -> Character:
    admin = db.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    character = Character(name=name, description="20岁，黑长直，白衬衫", owner_id=admin.id)
    if color_paths:
        character.portrait_path = save_character_bytes(_solid(720, 1280, RED), ".png")
        character.front_path = save_character_bytes(_solid(720, 1280, GREEN), ".png")
        character.side_path = save_character_bytes(_solid(720, 1280, BLUE), ".png")
        character.back_path = save_character_bytes(_solid(720, 1280, YELLOW), ".png")
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


def test_generate_face_first_four_views_then_wide(client, auth_header, monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_produce(provider, **kwargs):  # noqa: ANN001, ANN003
        calls.append(kwargs)
        prompt = kwargs.get("prompt", "")
        if any(marker in prompt for marker in ("面部特写", "正面全身", "侧面全身", "背面全身")):
            return [("view.png", _solid(864, 1536, _fake_slot_color(prompt)))]
        return [("wide.png", _solid(1536, 864, (90, 90, 90)))]

    with SessionLocal() as db:
        character = _character(db)
        job = _job(db, character.owner_id, character.id)
        _run(db, monkeypatch, job, fake_produce)
        db.refresh(character)

        assert len(calls) == 5
        assert [call["workflow"] for call in calls] == [
            "qwen_image_21",
            "qwen_image_21_edit",
            "qwen_image_21_edit_multi",
            "qwen_image_21_edit_multi",
            "qwen_image_21_edit_multi",
        ]
        assert "面部特写" in calls[0]["prompt"]
        assert "正面全身" in calls[1]["prompt"]
        assert "侧面全身" in calls[2]["prompt"]
        assert "背面全身" in calls[3]["prompt"]
        assert all(
            character.__getattribute__(f"{slot}_path")
            for slot in ("portrait", "front", "side", "back")
        )
        grid = Image.open(resolve(character.turnaround_grid_path)).convert("RGB")
        assert grid.size == (1152, 2048)
        assert grid.getpixel((288, 512)) == RED
        assert grid.getpixel((864, 512)) == GREEN
        assert grid.getpixel((288, 1536)) == BLUE
        assert grid.getpixel((864, 1536)) == YELLOW
        assert Image.open(resolve(character.turnaround_path)).size == (1536, 864)


def test_generate_body_first_starts_with_front(client, auth_header, monkeypatch) -> None:
    prompts: list[str] = []

    async def fake_produce(provider, **kwargs):  # noqa: ANN001, ANN003
        prompts.append(kwargs.get("prompt", ""))
        if "完整全身" in kwargs.get("prompt", "") or "面部特写" in kwargs.get("prompt", ""):
            return [("view.png", _solid(864, 1536, _fake_slot_color(kwargs["prompt"])))]
        return [("wide.png", _solid(1536, 864, (90, 90, 90)))]

    with SessionLocal() as db:
        character = _character(db, name="全身优先角色")
        job = _job(db, character.owner_id, character.id, order="body")
        _run(db, monkeypatch, job, fake_produce)
        assert "正面全身" in prompts[0]
        assert "面部特写" in prompts[1]


def test_full_slots_without_prompt_only_composes(client, auth_header, monkeypatch) -> None:
    async def fake_produce(provider, **kwargs):  # noqa: ANN001, ANN003
        raise AssertionError("四槽全满且无提示词时不应调用生成服务")

    with SessionLocal() as db:
        character = _character(db, color_paths=True, name="纯合成角色")
        old_front = character.front_path
        job = _job(
            db,
            character.owner_id,
            character.id,
            slots={
                "portrait": character.portrait_path,
                "front": character.front_path,
                "side": character.side_path,
                "back": character.back_path,
            },
            config={"mode": "compose", "workflows": {}, "model": ""},
        )
        _run(db, monkeypatch, job, fake_produce)
        db.refresh(character)
        assert character.front_path == old_front
        assert character.turnaround_grid_path
        assert character.turnaround_path
        assert _slot_color(resolve(character.front_path).read_bytes()) == _slot_color(
            resolve(old_front).read_bytes()
        )
        assert Image.open(resolve(character.turnaround_path)).size == (1920, 1080)


def test_modify_prompt_changes_only_target_view(client, auth_header, monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_produce(provider, **kwargs):  # noqa: ANN001, ANN003
        calls.append(kwargs)
        if "外套" in kwargs.get("prompt", ""):
            return [("view.png", _solid(864, 1536, MODIFIED))]
        return [("wide.png", _solid(1536, 864, (90, 90, 90)))]

    with SessionLocal() as db:
        character = _character(db, color_paths=True, name="修改角色")
        old_front = character.front_path
        old_portrait = character.portrait_path
        old_back = character.back_path
        supplement = save_character_bytes(_solid(800, 800, MAGENTA), ".png")
        job = _job(
            db,
            character.owner_id,
            character.id,
            prompt="把 <Picture 1> 的外套改成红色，参考 <Picture 2>",
            target_view="side",
            slots={
                "portrait": character.portrait_path,
                "front": character.front_path,
                "side": character.side_path,
                "back": character.back_path,
            },
            ref_image_path=supplement,
        )
        _run(db, monkeypatch, job, fake_produce)
        db.refresh(character)

        assert len(calls) == 2
        assert "外套" in calls[0]["prompt"]
        assert "image 1" in calls[0]["prompt"]
        assert "image 2" in calls[0]["prompt"]
        assert "<Picture" not in calls[0]["prompt"]
        assert _slot_color(resolve(calls[0]["inputs"]["image"]).read_bytes()) == BLUE
        assert _slot_color(resolve(calls[0]["inputs"]["image_2"]).read_bytes()) == MAGENTA
        assert character.front_path == old_front
        assert character.portrait_path == old_portrait
        assert character.back_path == old_back
        assert _slot_color(resolve(character.side_path).read_bytes()) == MODIFIED
        assert calls[1]["workflow"] == "qwen_image_21_edit_multi"


def test_generate_api_rejects_bad_view_upload(client, auth_header) -> None:
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={"name": "比例错误角色", "description": "黑长直"},
        files={"front": ("front.png", _solid(800, 1280, RED), "image/png")},
    )
    assert response.status_code == 400
    assert "9:16" in response.json()["detail"]

    small = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={"name": "小图角色", "description": "黑长直"},
        files={"front": ("front.png", _solid(600, 1067, RED), "image/png")},
    )
    assert small.status_code == 400
    assert "640" in small.json()["detail"]


def test_generate_api_requires_head_view(client, auth_header) -> None:
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={"name": "只有侧面", "description": "黑长直"},
        files={"side": ("side.png", _solid(720, 1280, BLUE), "image/png")},
    )
    assert response.status_code == 400
    assert "面部特写或正面全身" in response.json()["detail"]


def test_generate_api_reports_missing_config(client, auth_header) -> None:
    with SessionLocal() as db:
        provider = _create_provider(db, type_="comfyui", name="角色接口缺配置")
        for key in (
            "default_character_workflow",
            "default_character_i2i_workflow",
            "default_character_i2i_multi_workflow",
        ):
            set_str_pref(db, key, "")
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={
            "name": "缺配置角色",
            "description": "黑长直，白衬衫",
            "provider_id": str(provider.id),
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "character_config_missing"
    assert len(detail["missing"]) == 3
    config = client.get(
        f"/api/v1/characters/config?provider_id={provider.id}", headers=auth_header
    )
    assert config.status_code == 200
    assert len(config.json()["missing"]) == 3


def test_generate_api_full_slots_without_prompt_skips_config(client, auth_header) -> None:
    with SessionLocal() as db:
        provider = _create_provider(db, type_="comfyui", name="角色接口纯合成")
        for key in (
            "default_character_workflow",
            "default_character_i2i_workflow",
            "default_character_i2i_multi_workflow",
        ):
            set_str_pref(db, key, "")
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={
            "name": "纯合成接口角色",
            "description": "黑长直",
            "provider_id": str(provider.id),
        },
        files={
            "portrait": ("portrait.png", _solid(720, 1280, RED), "image/png"),
            "front": ("front.png", _solid(720, 1280, GREEN), "image/png"),
            "side": ("side.png", _solid(720, 1280, BLUE), "image/png"),
            "back": ("back.png", _solid(720, 1280, YELLOW), "image/png"),
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["kind"] == "character.generate"


def test_download_character_zip_contains_six_images(client, auth_header) -> None:
    with SessionLocal() as db:
        character = _character(db, color_paths=True, name="下载角色")
        character.turnaround_path = save_character_bytes(_solid(1920, 1080, (90, 90, 90)), ".png")
        character.turnaround_grid_path = save_character_bytes(
            compose_character_grid(
                {
                    "portrait": _solid(720, 1280, RED),
                    "front": _solid(720, 1280, GREEN),
                    "side": _solid(720, 1280, BLUE),
                    "back": _solid(720, 1280, YELLOW),
                }
            ),
            ".png",
        )
        db.commit()
        character_id = character.id
    response = client.get(f"/api/v1/characters/{character_id}/download", headers=auth_header)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-cache"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
    assert names == {
        "portrait.png",
        "front.png",
        "side.png",
        "back.png",
        "turnaround_grid.png",
        "turnaround.png",
        "character.json",
    }


def test_generate_api_rejects_clearing_both_head_slots(client, auth_header) -> None:
    with SessionLocal() as db:
        character = _character(db, color_paths=True, name="清空头部槽角色")
        character_id = character.id
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={
            "character_id": str(character_id),
            "cleared_slots": "portrait,front",
        },
    )
    assert response.status_code == 400
    assert "面部特写或正面全身" in response.json()["detail"]


def test_character_prompt_tasks_are_available() -> None:
    from liberastra.services.prompts import build_system_prompt

    appearance = build_system_prompt("character_appearance", user_prompt="20岁，黑长直")
    edit = build_system_prompt("character_edit", user_prompt="把外套改成红色")
    assert "外观" in appearance
    assert "四宫格" in appearance
    assert "保持不变" in edit
    assert "image 1" in edit


def test_generate_api_description_mode_accepts_reference_only(client, auth_header) -> None:
    with SessionLocal() as db:
        provider = _create_provider(db, type_="comfyui", name="角色接口仅参考图")
        set_str_pref(db, "default_character_workflow", "qwen_image_21")
        set_str_pref(db, "default_character_i2i_workflow", "qwen_image_21_edit")
        set_str_pref(db, "default_character_i2i_multi_workflow", "qwen_image_21_edit_multi")
    response = client.post(
        "/api/v1/characters/generate",
        headers=auth_header,
        data={"name": "只有参考图角色", "provider_id": str(provider.id)},
        files={"ref_images": ("ref.png", _solid(720, 1280, RED), "image/png")},
    )
    assert response.status_code == 202, response.text
    assert response.json()["kind"] == "character.generate"


def test_single_image_edit_pack_translates_picture_alias() -> None:
    from liberastra.services.canvas_graph import translate_prompt_slots
    from liberastra.services.workflows import get_pack

    pack = get_pack("qwen_image_21_edit")
    assert translate_prompt_slots("保留 <Picture 1> 的脸", pack.inputs) == "保留 原图 的脸"

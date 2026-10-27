"""提示词库种子、列表 API、默认 LLM 偏好与 build_system_prompt。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from liberastra.core.config import get_settings
from liberastra.core.db import SessionLocal
from liberastra.services.preferences import all_prefs, set_pref, set_str_pref
from liberastra.services.prompts import (
    build_system_prompt,
    ensure_prompt_store,
    list_scenes,
    list_tasks,
)
from liberastra.services.providers import pick_llm_with_model


def test_ensure_prompt_store_seeds_files(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LIBERASTRA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    root = ensure_prompt_store()
    assert (root / "tasks.yaml").exists()
    assert (root / "scenes.yaml").exists()
    tasks = list_tasks()
    ids = {t["id"] for t in tasks}
    assert "t2i" in ids and "i2v" in ids and "quick_topic" in ids
    scenes = list_scenes()
    assert any(s["id"] == "poster" for s in scenes)
    get_settings.cache_clear()


def test_build_system_prompt_includes_scene_and_task() -> None:
    text = build_system_prompt(
        "t2i", scene="poster", aspect="9:16", user_prompt="一只橘猫坐在窗边"
    )
    assert "当前功能" in text and "t2i" in text
    assert "六槽位" in text or "主体" in text
    assert "海报" in text or "主标题" in text
    assert "9:16" in text
    assert "中文" in text


def test_build_system_prompt_auto_keeps_task() -> None:
    text = build_system_prompt("i2v", scene="auto", user_prompt="slow camera pan")
    assert "当前功能" in text and "i2v" in text
    assert "English" in text or "英文" in text or "跟随" in text


def test_list_prompts_api(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.get("/api/v1/prompts", headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert "tasks" in body and "scenes" in body
    assert any(t["id"] == "t2i" for t in body["tasks"])


def test_prompt_template_override_roundtrip(client: TestClient, auth_header: dict[str, str]) -> None:
    """覆盖 → custom 标记 → 删除覆盖恢复默认;内置未覆盖条目删除报 400。"""
    put = client.put(
        "/api/v1/prompts/tasks/t2i",
        json={"name": "文生图", "system": "自定义系统提示词"},
        headers=auth_header,
    )
    assert put.status_code == 200, put.text
    body = client.get("/api/v1/prompts", headers=auth_header).json()
    t2i = next(t for t in body["tasks"] if t["id"] == "t2i")
    assert t2i["custom"] is True
    assert t2i["system"] == "自定义系统提示词"

    # 删除覆盖 = 恢复默认
    delete = client.delete("/api/v1/prompts/tasks/t2i", headers=auth_header)
    assert delete.status_code == 204
    body = client.get("/api/v1/prompts", headers=auth_header).json()
    t2i = next(t for t in body["tasks"] if t["id"] == "t2i")
    assert t2i["custom"] is False
    assert "自定义系统提示词" not in t2i["system"]

    # 未自定义的内置条目不可删
    again = client.delete("/api/v1/prompts/tasks/t2i", headers=auth_header)
    assert again.status_code == 400

    # 场景预设同款
    client.put(
        "/api/v1/prompts/scenes/photo",
        json={"name": "摄影", "append": "自定义叠加"},
        headers=auth_header,
    )
    body = client.get("/api/v1/prompts", headers=auth_header).json()
    assert next(s for s in body["scenes"] if s["id"] == "photo")["custom"] is True
    assert client.delete("/api/v1/prompts/scenes/photo", headers=auth_header).status_code == 204
    body = client.get("/api/v1/prompts", headers=auth_header).json()
    assert next(s for s in body["scenes"] if s["id"] == "photo")["custom"] is False


def test_preferences_default_llm(client: TestClient, auth_header: dict[str, str]) -> None:
    before = client.get("/api/v1/system/preferences", headers=auth_header).json()
    assert "default_llm_provider_id" in before
    assert "default_llm_model" in before

    patched = client.patch(
        "/api/v1/system/preferences",
        json={"default_llm_provider_id": 0, "default_llm_model": "qwen2.5"},
        headers=auth_header,
    )
    assert patched.status_code == 200
    assert patched.json()["default_llm_model"] == "qwen2.5"

    db = SessionLocal()
    try:
        prefs = all_prefs(db)
        assert prefs["default_llm_model"] == "qwen2.5"
        set_str_pref(db, "default_llm_model", "")
        set_pref(db, "default_llm_provider_id", 0)
    finally:
        db.close()


def test_pick_llm_with_model_uses_pref_model(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/providers",
        json={
            "name": "测试 LLM",
            "type": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "extra": {},
            "models": ["alpha", "beta"],
        },
        headers=auth_header,
    )
    assert created.status_code == 201
    pid = created.json()["id"]

    client.patch(
        "/api/v1/system/preferences",
        json={"default_llm_provider_id": pid, "default_llm_model": "beta"},
        headers=auth_header,
    )

    db = SessionLocal()
    try:
        provider, model = pick_llm_with_model(db)
        assert provider.id == pid
        assert model == "beta"
        provider2, model2 = pick_llm_with_model(db, provider_id=pid, model="alpha")
        assert provider2.id == pid
        assert model2 == "alpha"
    finally:
        db.close()

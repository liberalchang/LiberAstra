"""供应商目录、火山请求体、执行契约与画布菜单。pytest 直接收集本文件。"""

import base64

import pytest
from fastapi.testclient import TestClient

from liberastra.providers.base import ProviderError
from liberastra.providers.catalog import (
    classify_model_id,
    default_canvas_menu,
    media_slots,
    merge_catalog,
    normalize_menu_item,
    pack_sub_capability,
)
from liberastra.providers.vendors.volcengine.presets import presets_for
from liberastra.providers.vendors.volcengine.schemas import video_body
from liberastra.providers.vendors.volcengine.speech import collect_tts_audio


def test_merge_keeps_user_switch_and_custom_endpoint() -> None:
    presets = presets_for("volcengine_ark")
    existing = [
        {
            "id": "doubao-seedance-2-5-260628",
            "label": "我的 Seedance",
            "category": "video",
            "sub_capabilities": ["t2v", "i2v_first", "i2v_flf", "v2v_ref"],
            "enabled": False,
            "custom": False,
        },
        {
            "id": "ep-custom",
            "label": "接入点",
            "category": "video",
            "sub_capabilities": ["t2v"],
            "enabled": True,
            "custom": True,
        },
    ]
    merged = merge_catalog(existing, ["doubao-seedream-new"], presets)
    by_id = {item["id"]: item for item in merged}
    assert by_id["doubao-seedance-2-5-260628"]["enabled"] is False
    assert by_id["doubao-seedance-2-5-260628"]["label"] == "我的 Seedance"
    assert by_id["ep-custom"]["custom"] is True
    assert by_id["doubao-seedream-new"]["category"] == "unknown"
    assert by_id["doubao-seedream-new"]["sub_capabilities"] == []
    assert by_id["doubao-seedream-5-0-lite-260128"]["enabled"] is True


def test_provider_type_places_models_without_reading_the_name() -> None:
    """服务商类型决定归类。ComfyUI 检查点不进功能，Edge 音色进文字转语音。"""
    from liberastra.providers.catalog import classify_remote

    ollama = classify_remote("ollama", "llama3")
    assert ollama is not None
    assert ollama["category"] == "llm"
    assert ollama["sub_capabilities"] == ["chat"]
    embedding = classify_remote("ollama", "bge-m3:latest")
    assert embedding is not None
    assert embedding["category"] == "unknown"
    assert embedding["sub_capabilities"] == []
    reranker = classify_remote("ollama", "bge-reranker-v2-m3:latest")
    assert reranker is not None
    assert reranker["sub_capabilities"] == []
    checkpoint = classify_remote("comfyui", "flux-dev.safetensors")
    assert checkpoint is not None
    assert checkpoint["category"] == "unknown"
    assert checkpoint["sub_capabilities"] == []
    voice = classify_remote("edge_tts", "zh-CN-XiaoxiaoNeural")
    assert voice is not None
    assert voice["sub_capabilities"] == ["tts"]


def test_classify_prefixes() -> None:
    from liberastra.providers.catalog import resolve_model_capabilities

    unknown = classify_model_id("some-chat-model")
    assert unknown is not None
    assert unknown["sub_capabilities"] == []
    assert resolve_model_capabilities("volcengine_ark", "doubao-seedance-2-0-260128") == [
        "t2v",
        "i2v_first",
        "i2v_flf",
        "v2v_ref",
    ]


def test_seedance_25_first_last_locks_adaptive_ratio() -> None:
    body = video_body(
        model="doubao-seedance-2-5-260628",
        prompt="从白天走到夜晚",
        sub_capability="i2v_flf",
        images={
            "first_frame": ["data:image/png;base64,aa"],
            "last_frame": ["data:image/png;base64,bb"],
        },
        ratio="16:9",
    )
    roles = [part.get("role") for part in body["content"] if part["type"] == "image_url"]
    assert roles == ["first_frame", "last_frame"]
    assert body["ratio"] == "adaptive"
    assert "reference_image" not in roles


def test_text_to_video_has_only_text() -> None:
    body = video_body(
        model="doubao-seedance-1-5-pro-251215",
        prompt="海面",
        sub_capability="t2v",
    )
    assert body["content"] == [{"type": "text", "text": "海面"}]


def test_first_last_requires_both_frames() -> None:
    with pytest.raises(ProviderError):
        video_body(
            model="doubao-seedance-2-0-260128",
            prompt="转场",
            sub_capability="i2v_flf",
            images={"first_frame": ["data:image/png;base64,aa"]},
        )


def test_menu_title_length() -> None:
    item = default_canvas_menu()[0]
    assert 2 <= len(item["title"]) <= 8
    with pytest.raises(ValueError):
        normalize_menu_item({**item, "title": "太"})


def test_collect_tts_audio_lines() -> None:
    payload = base64.b64encode(b"audio-bytes").decode("ascii")
    audio = collect_tts_audio(f'{{"code":0,"data":"{payload}"}}\n')
    assert audio == b"audio-bytes"


def test_ark_provider_seeds_catalog(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/providers",
        json={"name": "方舟", "type": "volcengine_ark", "api_key": "ark-key"},
        headers=auth_header,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    catalog = body["extra"]["model_catalog"]
    assert any(item["id"].startswith("doubao-seedance") and item["enabled"] for item in catalog)
    assert "doubao-seedance-2-5-260628" in body["models"]

    catalog[0]["enabled"] = not catalog[0]["enabled"]
    saved = client.put(
        f"/api/v1/providers/{body['id']}/catalog",
        json={"models": catalog},
        headers=auth_header,
    )
    assert saved.status_code == 200


def test_execution_specs_and_canvas_menu(client: TestClient, auth_header: dict[str, str]) -> None:
    specs = client.get(
        "/api/v1/providers/execution-specs",
        params={"sub_capability": "i2v_first"},
        headers=auth_header,
    )
    assert specs.status_code == 200, specs.text
    rows = specs.json()
    assert rows
    assert all(row["sub_capability"] == "i2v_first" for row in rows)
    assert any(row["target_type"] == "workflow" for row in rows)

    menu = client.get("/api/v1/canvases/menu", headers=auth_header)
    assert menu.status_code == 200
    titles = {item["title"] for item in menu.json()}
    assert "首帧生视频" in titles

    rejected = client.put(
        "/api/v1/canvases/menu",
        json=[{**menu.json()[0], "title": "一"}],
        headers=auth_header,
    )
    assert rejected.status_code == 400


def test_workflow_packs_keep_their_own_functions() -> None:
    """环绕、调色、重绘不能被压进参考视频或多图编辑。"""
    assert pack_sub_capability("minimax_h3_orbit", "i2v", 2) == "i2v_orbit"
    assert pack_sub_capability("qwen_edit_2511_color_grade", "i2i", 2) == "color_grade"
    assert pack_sub_capability("qwen_image_21_inpaint", "i2i", 2) == "inpaint"
    titles = {item["title"]: item["sub_capability"] for item in default_canvas_menu()}
    assert titles["360全景"] == "i2v_orbit"
    assert titles["摄影调色"] == "color_grade"


def test_every_workflow_pack_has_a_menu_function() -> None:
    from liberastra.services.workflows import list_packs

    menu_subs = {item["sub_capability"] for item in default_canvas_menu()}
    missing = []
    for pack in list_packs():
        image_count = sum(
            1 for spec in pack.inputs.values() if isinstance(spec, dict) and spec.get("type") == "image"
        )
        sub = pack_sub_capability(pack.name, pack.capability, image_count)
        if sub not in menu_subs:
            missing.append(f"{pack.name}:{sub}")
    assert missing == []
    slots = media_slots("t2i")
    assert any(slot["type"] == "text" and slot["required"] for slot in slots)


def test_manual_bind_returns_only_checked_targets() -> None:
    from liberastra.providers.catalog import targets_for_menu_item

    item = normalize_menu_item(
        {
            "id": "custom_orbit",
            "category": "video",
            "title": "360全景",
            "sub_capability": "i2v_orbit",
            "bind_mode": "manual",
            "manual_targets": [{"target_type": "workflow", "target_id": "minimax_h3_orbit"}],
        }
    )
    specs = [
        {"target_type": "workflow", "target_id": "minimax_h3_orbit", "sub_capability": "i2v_orbit"},
        {"target_type": "workflow", "target_id": "minimax_h3_i2v", "sub_capability": "i2v_first"},
    ]
    chosen = targets_for_menu_item(item, specs)
    assert [row["target_id"] for row in chosen] == ["minimax_h3_orbit"]


def test_menu_can_add_an_item(client: TestClient, auth_header: dict[str, str]) -> None:
    current = client.get("/api/v1/canvases/menu", headers=auth_header)
    assert current.status_code == 200
    extra = {
        **current.json()[0],
        "id": "custom_grade",
        "title": "自定义调色",
        "category": "image",
        "sub_capability": "color_grade",
    }
    saved = client.put(
        "/api/v1/canvases/menu",
        json=[*current.json(), extra],
        headers=auth_header,
    )
    assert saved.status_code == 200, saved.text
    assert any(item["id"] == "custom_grade" for item in saved.json())


def test_same_vendor_can_be_configured_twice(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    first = client.post(
        "/api/v1/providers",
        json={"name": "方舟甲", "type": "volcengine_ark", "api_key": "key-a"},
        headers=auth_header,
    )
    second = client.post(
        "/api/v1/providers",
        json={"name": "方舟乙", "type": "volcengine_ark", "api_key": "key-b"},
        headers=auth_header,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]


def test_seedance_25_first_frame_is_a_menu_function() -> None:
    seedance = next(
        item for item in presets_for("volcengine_ark") if item["id"] == "doubao-seedance-2-5-260628"
    )
    assert set(seedance["sub_capabilities"]) == {"t2v", "i2v_first", "i2v_flf", "v2v_ref"}
    first = next(item for item in default_canvas_menu() if item["sub_capability"] == "i2v_first")
    assert first["title"] == "首帧生视频"
    assert any(slot["key"] == "first_frame" for slot in media_slots("i2v_first"))


def test_each_function_keeps_its_required_upstream_inputs() -> None:
    """前置节点跟实际执行输入走。口播和动作迁移的提示词由执行器补，不另建文本。"""
    from liberastra.providers.schema_registry import workflow_specs
    from liberastra.services.workflows import list_packs

    specs = {item.target_id: item for item in workflow_specs(list_packs())}

    def types_of(name: str) -> list[str]:
        return [slot.type for slot in specs[name].media_slots if slot.required]

    assert "text" in types_of("qwen_image_21")
    assert "text" in types_of("minimax_h3_i2v")
    assert "image" in types_of("minimax_h3_i2v")
    assert "text" not in types_of("minimax_h3_motion")
    assert "video" in types_of("minimax_h3_motion")
    assert any(slot.input_kind == "character" for slot in specs["minimax_h3_motion"].media_slots)
    assert "text" not in types_of("qwen_edit_2511_color_grade")
    assert types_of("qwen_edit_2511_color_grade").count("image") == 2
    assert "text" not in types_of("minimax_h3_orbit")
    assert "text" not in types_of("minimax_h3_avatar")
    assert "audio" in types_of("minimax_h3_avatar")
    assert "image" in types_of("minimax_h3_avatar")


def test_model_placement_uses_the_capability_registry() -> None:
    """只有能力表里写明的模型才能进入功能。名字像不像不作为依据。"""
    from liberastra.providers.catalog import resolve_model_capabilities

    assert resolve_model_capabilities("volcengine_ark", "doubao-seedance-2-5-260628") == [
        "t2v",
        "i2v_first",
        "i2v_flf",
        "v2v_ref",
    ]
    assert resolve_model_capabilities("volcengine_ark", "doubao-seedream-5-0-lite-260128") == [
        "t2i",
        "i2i_single",
        "i2i_multi",
    ]
    unknown = classify_model_id("some-brand-new-model")
    assert unknown is not None
    assert unknown["sub_capabilities"] == []
    assert unknown["category"] == "unknown"


def test_old_saved_menu_receives_later_factory_functions(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """已经保存过的旧菜单，在读的时候补上后来新增的出厂功能。用户之后删掉的项保持删除。"""
    import json

    from liberastra.api.routes.canvases import MENU_SETTING_KEY
    from liberastra.core.db import SessionLocal
    from liberastra.models import AppSetting

    dropped = {"color_grade", "i2v_orbit", "inpaint", "video_analysis"}
    old = [item for item in default_canvas_menu() if item["sub_capability"] not in dropped]
    db = SessionLocal()
    try:
        row = db.get(AppSetting, MENU_SETTING_KEY)
        payload = json.dumps(old, ensure_ascii=False)
        if row is None:
            db.add(AppSetting(key=MENU_SETTING_KEY, value=payload))
        else:
            row.value = payload
        db.commit()
    finally:
        db.close()

    loaded = client.get("/api/v1/canvases/menu", headers=auth_header)
    assert loaded.status_code == 200, loaded.text
    subs = {item["sub_capability"] for item in loaded.json()}
    assert dropped <= subs
    assert loaded.json()[0]["media_slots"]

    kept = [item for item in loaded.json() if item["sub_capability"] != "color_grade"]
    saved = client.put("/api/v1/canvases/menu", json=kept, headers=auth_header)
    assert saved.status_code == 200, saved.text
    again = {item["sub_capability"] for item in client.get("/api/v1/canvases/menu", headers=auth_header).json()}
    assert "color_grade" not in again
    assert "i2v_orbit" in again

    client.put("/api/v1/canvases/menu", json=default_canvas_menu(), headers=auth_header)


def test_normalize_keeps_typed_params_and_drops_the_rest() -> None:
    from liberastra.providers.catalog import normalize_model_item

    chat = normalize_model_item(
        {
            "id": "deepseek-chat",
            "category": "llm",
            "sub_capabilities": ["chat"],
            "params": {"max_output": "8192", "defaults": {"duration": 8}, "reasoning": "high"},
        }
    )
    assert chat["params"] == {"max_output": 8192}

    image = normalize_model_item(
        {
            "id": "seedream",
            "category": "image",
            "sub_capabilities": ["t2i"],
            "params": {"max_output": 100, "defaults": {"size": "1024x1024", "watermark": "false", "seed": 7}},
        }
    )
    assert image["params"]["defaults"] == {"size": "1024x1024", "watermark": False}
    assert "max_output" not in image["params"]

    unknown = normalize_model_item(
        {
            "id": "bge-m3",
            "category": "unknown",
            "sub_capabilities": ["chat"],
            "params": {"max_output": 100},
        }
    )
    assert unknown["category"] == "unknown"
    assert unknown["sub_capabilities"] == []
    assert "params" not in unknown


def test_model_specs_use_saved_image_defaults() -> None:
    from types import SimpleNamespace

    from liberastra.providers.schema_registry import model_specs

    provider = SimpleNamespace(
        id=1,
        type="volcengine_ark",
        name="ark",
        extra={
            "model_catalog": [
                {
                    "id": "seedream",
                    "label": "Seedream",
                    "category": "image",
                    "sub_capabilities": ["t2i"],
                    "enabled": True,
                    "custom": True,
                    "params": {"defaults": {"size": "1024x1024"}},
                }
            ]
        },
    )
    specs = model_specs(provider)
    t2i = next(spec for spec in specs if spec.sub_capability == "t2i")
    assert t2i.inputs["size"]["default"] == "1024x1024"
    assert t2i.inputs["output_format"]["default"] == "png"


def test_chat_options_use_model_max_output() -> None:
    from types import SimpleNamespace

    from liberastra.services.llm import _chat_options

    provider = SimpleNamespace(
        extra={
            "model_catalog": [
                {
                    "id": "deepseek-chat",
                    "label": "DeepSeek",
                    "category": "llm",
                    "sub_capabilities": ["chat"],
                    "enabled": True,
                    "custom": True,
                    "params": {"max_output": 2048},
                }
            ]
        }
    )
    assert _chat_options(provider, "deepseek-chat", {})["max_tokens"] == 2048
    assert "max_tokens" not in _chat_options(provider, "other", {})
    assert _chat_options(provider, "deepseek-chat", {"max_tokens": 10})["max_tokens"] == 10

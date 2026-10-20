"""工作流包加载、参数注入与导入/删除测试。"""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from liberastra.providers.base import ProviderError
from liberastra.services.workflows import (
    WorkflowPack,
    apply_accel,
    apply_inputs,
    delete_pack,
    extract_accel,
    get_pack,
    import_pack,
    list_packs,
    validate_pack,
)

MINI_WORKFLOW = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 1]}},
    "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m.safetensors"}},
}

MINI_MANIFEST_INPUTS = {
    "prompt": {"node": "1", "field": "inputs.text", "type": "str", "required": True},
    "steps": {"node": "1", "field": "inputs.steps", "type": "int", "default": 20, "min": 1, "max": 50},
}

# UNET → Turbo LoRA → Guider；Scheduler 单独挂 steps
ACCEL_WORKFLOW = {
    "10": {"class_type": "UNETLoader", "inputs": {"unet_name": "h3.safetensors"}},
    "200": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"model": ["10", 0], "lora_name": "placeholder.safetensors", "strength": 1.0},
    },
    "20": {"class_type": "BasicGuider", "inputs": {"model": ["200", 0]}},
    "9": {"class_type": "BasicScheduler", "inputs": {"steps": 20, "scheduler": "simple"}},
    "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
}

ACCEL_MANIFEST = {
    "capability": "i2v",
    "inputs": {
        "steps": {"node": "9", "field": "inputs.steps", "type": "int", "default": 20},
        "sampler_name": {
            "node": "17",
            "field": "inputs.sampler_name",
            "type": "str",
            "default": "res_multistep",
        },
    },
    "outputs": {"node": "20"},
    "accel": {
        "label": "Turbo 加速",
        "default_enabled": False,
        "node": "200",
        "bypass_input": "model",
        "lora": {
            "field": "inputs.lora_name",
            "recommended": "minimax_h3_turbo_v4_step600_ema.safetensors",
        },
        "strength": {"field": "inputs.strength", "default": 1.0},
        "preset": {"steps": 8, "sampler_name": "euler"},
    },
}


def test_builtin_pack_loads() -> None:
    packs = list_packs()
    assert any(p.name == "t2i_basic" and p.source == "builtin" for p in packs)
    pack = get_pack("t2i_basic")
    assert pack.capability == "t2i"
    assert "prompt" in pack.inputs


def test_minimax_h3_i2v_accel_roundtrip() -> None:
    pack = get_pack("minimax_h3_i2v")
    assert pack.fps == 24
    assert pack.accel.get("node") == "105:200"
    values = {"prompt": "test", "seed": 1, "image": "uploads/x.png"}
    # 关闭：摘掉 Turbo LoRA，Guider/Scheduler 改接回 UNET
    off = apply_accel(apply_inputs(pack, values), pack, {"enabled": False}, user_values=values)
    assert "105:200" not in off
    assert off["105:16"]["inputs"]["model"] == ["105:6", 0]
    assert off["105:9"]["inputs"]["model"] == ["105:6", 0]
    assert off["105:9"]["inputs"]["steps"] == 20
    # 开启：注入 LoRA + preset 步数
    on = apply_accel(
        apply_inputs(pack, values),
        pack,
        {
            "enabled": True,
            "lora": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            "strength": 1.0,
        },
        user_values=values,
    )
    assert on["105:200"]["inputs"]["lora_name"] == "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
    assert on["105:9"]["inputs"]["steps"] == 8


def test_minimax_h3_enhancer_pack_loads() -> None:
    pack = get_pack("minimax_h3_i2v_enhancer")
    assert "MiniMaxH3PromptEnhancer" in (pack.requirements.get("nodes") or [])
    assert pack.accel.get("node") == "105:200"
    assert isinstance(pack.outputs.get("texts"), list) and len(pack.outputs["texts"]) == 2
    values = {"prompt": "一只猫在跑", "seed": 2, "image": "uploads/x.png"}
    wf = apply_inputs(pack, values)
    assert wf["105:122"]["inputs"]["manual_prompt"] == "一只猫在跑"
    assert wf["105:104"]["inputs"]["prompt"] == ["105:122", 0]
    # E5：关闭加速时摘掉 LoRA，Guider/Scheduler 改接 UNET
    off = apply_accel(wf, pack, {"enabled": False}, user_values=values)
    assert "105:200" not in off
    assert off["105:16"]["inputs"]["model"] == ["105:6", 0]
    assert off["105:9"]["inputs"]["model"] == ["105:6", 0]


def test_minimax_h3_i2v_uncensored_pack() -> None:
    """图生越狱无增强：heretic NVFP4 + LightX2V 8-step；保留 first_frame。"""
    unc = get_pack("minimax_h3_i2v_uncensored")
    assert unc.capability == "i2v"
    assert "image" in unc.inputs
    assert unc.workflow["105:104"]["inputs"]["first_frame"] == ["114", 0]
    assert unc.workflow["105:13"]["inputs"]["clip_name"] == "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors"
    assert "fl2v_turbo_8step" in unc.workflow["105:200"]["inputs"]["lora_name"]
    assert "MiniMaxH3PromptEnhancer" not in (unc.requirements.get("nodes") or [])
    values = {"prompt": "画中人转身", "seed": 6, "image": "uploads/x.png"}
    uwf = apply_inputs(unc, values)
    # image 类型由上传后 inject，apply_inputs 不改写 LoadImage
    assert uwf["105:104"]["inputs"]["prompt"] == "画中人转身"
    assert "114" in uwf
    uoff = apply_accel(uwf, unc, {"enabled": False}, user_values=values)
    assert "105:200" not in uoff
    uon = apply_accel(
        apply_inputs(unc, values),
        unc,
        {
            "enabled": True,
            "lora": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            "strength": 1.0,
        },
        user_values=values,
    )
    assert uon["105:9"]["inputs"]["steps"] == 8


def test_minimax_h3_t2v_packs() -> None:
    """文生视频：官方 + 越狱增强 + 越狱无增强；无首帧节点。"""
    t2v = get_pack("minimax_h3_t2v")
    assert t2v.capability == "t2v"
    assert "image" not in t2v.inputs
    assert "114" not in t2v.workflow
    assert "first_frame" not in t2v.workflow["105:104"]["inputs"]
    wf = apply_inputs(t2v, {"prompt": "海边日落", "seed": 3})
    assert wf["105:104"]["inputs"]["prompt"] == "海边日落"

    enh = get_pack("minimax_h3_t2v_enhancer")
    assert enh.capability == "t2v"
    assert "image" not in enh.inputs
    assert "114" not in enh.workflow
    assert "image" not in enh.workflow["105:122"]["inputs"]
    assert "first_frame" not in enh.workflow["105:104"]["inputs"]
    ewf = apply_inputs(enh, {"prompt": "城市夜景", "seed": 4})
    assert ewf["105:122"]["inputs"]["manual_prompt"] == "城市夜景"
    assert ewf["105:13"]["inputs"]["clip_name"].startswith("qwen3vl_32b_h3_ultra_uncensored")
    off = apply_accel(ewf, enh, {"enabled": False}, user_values={"prompt": "城市夜景"})
    assert "105:200" not in off

    unc = get_pack("minimax_h3_t2v_uncensored")
    assert unc.capability == "t2v"
    assert "image" not in unc.inputs
    assert "first_frame" not in unc.workflow["105:104"]["inputs"]
    assert unc.workflow["105:13"]["inputs"]["clip_name"] == "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors"
    assert "fl2v_turbo_8step" in unc.workflow["105:200"]["inputs"]["lora_name"]
    uwf = apply_inputs(unc, {"prompt": "民国上海", "seed": 5})
    assert uwf["105:104"]["inputs"]["prompt"] == "民国上海"
    uoff = apply_accel(uwf, unc, {"enabled": False}, user_values={"prompt": "民国上海"})
    assert "105:200" not in uoff
    uon = apply_accel(
        apply_inputs(unc, {"prompt": "民国上海"}),
        unc,
        {
            "enabled": True,
            "lora": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            "strength": 1.0,
        },
        user_values={"prompt": "民国上海"},
    )
    assert uon["105:9"]["inputs"]["steps"] == 8


def test_extract_texts_from_declared_nodes() -> None:
    from liberastra.providers.comfyui.workflow import extract_texts
    from liberastra.services.workflows import WorkflowPack

    pack = WorkflowPack(
        name="t",
        capability="i2v",
        description="",
        inputs={},
        outputs={
            "node": "92",
            "texts": [
                {"node": "123", "label": "增强后提示词"},
                {"node": "124", "label": "增强报告"},
            ],
        },
        workflow={},
        source="builtin",
    )
    client_out = {
        "123": {"text": ["detailed shot list ..."]},
        "124": {"ui": {"text": ["ok, no warnings"]}},
        "92": {"images": []},
    }
    texts = extract_texts(client_out, pack)
    assert len(texts) == 2
    assert texts[0].startswith("【增强后提示词】")
    assert "detailed shot list" in texts[0]
    assert texts[1].startswith("【增强报告】")
    assert "ok, no warnings" in texts[1]


def test_apply_inputs_injects_and_clamps() -> None:
    pack = get_pack("t2i_basic")
    workflow = apply_inputs(
        pack,
        {"prompt": "一只猫", "width": 99999, "height": 512, "seed": -1, "ckpt_name": "flux.safetensors"},
    )
    assert workflow["6"]["inputs"]["text"] == "一只猫"
    assert workflow["5"]["inputs"]["height"] == 512
    assert workflow["5"]["inputs"]["width"] == 4096  # clamp 到 max
    assert workflow["3"]["inputs"]["seed"] != -1  # 随机化
    assert workflow["4"]["inputs"]["ckpt_name"] == "flux.safetensors"


def test_qwen_pack_sets_batch_size() -> None:
    pack = get_pack("qwen_image_21")
    workflow = apply_inputs(pack, {"prompt": "一只猫", "batch_size": 3, "seed": 7})
    assert workflow["6"]["inputs"]["batch_size"] == 3
    assert workflow["5"]["inputs"]["prompt"] == "一只猫"
    assert workflow["7"]["inputs"]["seed"] == 7
    assert workflow["7"]["inputs"]["cfg"] == 1


def test_apply_inputs_missing_required() -> None:
    pack = get_pack("t2i_basic")
    with pytest.raises(ProviderError, match="必填"):
        apply_inputs(pack, {"width": 512})


def test_import_and_delete_pack() -> None:
    pack = import_pack(
        "test_pack",
        MINI_WORKFLOW,
        {"capability": "t2i", "inputs": MINI_MANIFEST_INPUTS, "outputs": {"node": "1"}},
    )
    assert pack.source == "user"
    assert get_pack("test_pack").inputs["prompt"]["required"] is True

    with pytest.raises(ProviderError, match="已存在"):
        import_pack("test_pack", MINI_WORKFLOW, {"inputs": MINI_MANIFEST_INPUTS})

    delete_pack("test_pack")
    with pytest.raises(ProviderError, match="不存在"):
        get_pack("test_pack")


def test_import_rejects_bad_node_mapping() -> None:
    with pytest.raises(ProviderError, match="不存在的节点"):
        import_pack(
            "bad_pack",
            MINI_WORKFLOW,
            {"inputs": {"prompt": {"node": "99", "field": "inputs.text"}}},
        )


def _accel_pack() -> WorkflowPack:
    return import_pack("accel_pack", deepcopy(ACCEL_WORKFLOW), deepcopy(ACCEL_MANIFEST), overwrite=True)


def test_extract_accel_strips_reserved_key() -> None:
    clean, accel = extract_accel({"steps": 12, "__accel": {"enabled": True, "lora": "a.safetensors"}})
    assert clean == {"steps": 12}
    assert accel == {"enabled": True, "lora": "a.safetensors"}


def test_apply_accel_enabled_sets_lora_strength_and_preset() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {})
        workflow = apply_accel(
            workflow,
            pack,
            {"enabled": True, "lora": "turbo.safetensors", "strength": 1.1},
            user_values={},
        )
        assert workflow["200"]["inputs"]["lora_name"] == "turbo.safetensors"
        assert workflow["200"]["inputs"]["strength"] == 1.1
        assert workflow["9"]["inputs"]["steps"] == 8
        assert workflow["17"]["inputs"]["sampler_name"] == "euler"
        assert "200" in workflow
        assert workflow["20"]["inputs"]["model"] == ["200", 0]
    finally:
        delete_pack("accel_pack")


def test_apply_accel_user_values_override_preset() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {"steps": 12})
        workflow = apply_accel(
            workflow,
            pack,
            {"enabled": True, "lora": "turbo.safetensors"},
            user_values={"steps": 12},
        )
        assert workflow["9"]["inputs"]["steps"] == 12  # 用户值优先
        assert workflow["17"]["inputs"]["sampler_name"] == "euler"  # preset 补齐
    finally:
        delete_pack("accel_pack")


def test_apply_accel_disabled_rewires_and_removes_node() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {"steps": 20})
        workflow = apply_accel(workflow, pack, {"enabled": False}, user_values={"steps": 20})
        assert "200" not in workflow
        assert workflow["20"]["inputs"]["model"] == ["10", 0]
        assert workflow["9"]["inputs"]["steps"] == 20
        # 图里不应残留对已删节点的引用
        for node in workflow.values():
            for value in node.get("inputs", {}).values():
                if isinstance(value, list) and len(value) == 2:
                    assert str(value[0]) != "200"
    finally:
        delete_pack("accel_pack")


def test_apply_accel_default_disabled_when_omitted() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {})
        workflow = apply_accel(workflow, pack, None, user_values={})
        assert "200" not in workflow
        assert workflow["20"]["inputs"]["model"] == ["10", 0]
    finally:
        delete_pack("accel_pack")


def test_pack_without_accel_unchanged() -> None:
    pack = get_pack("t2i_basic")
    assert pack.accel == {}
    values = {"prompt": "猫", "seed": 1, "ckpt_name": "m.safetensors"}
    before = apply_inputs(pack, values)
    after = apply_accel(before, pack, {"enabled": True}, user_values=values)
    assert after == before


def test_import_rejects_accel_without_link() -> None:
    bad = deepcopy(ACCEL_WORKFLOW)
    bad["200"]["inputs"]["model"] = "not-a-link"
    with pytest.raises(ProviderError, match="连线"):
        import_pack("bad_accel", bad, deepcopy(ACCEL_MANIFEST))


def test_apply_accel_rejects_bad_strength() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {})
        with pytest.raises(ProviderError, match="强度"):
            apply_accel(
                workflow,
                pack,
                {"enabled": True, "lora": "turbo.safetensors", "strength": "abc"},
                user_values={},
            )
    finally:
        delete_pack("accel_pack")


def test_apply_accel_rejects_string_enabled() -> None:
    pack = _accel_pack()
    try:
        workflow = apply_inputs(pack, {})
        with pytest.raises(ProviderError, match="布尔"):
            apply_accel(workflow, pack, {"enabled": "false"}, user_values={})
    finally:
        delete_pack("accel_pack")


def test_convert_canvas_to_api_and_manifest() -> None:
    from liberastra.services.canvas_convert import convert_comfy_json, is_canvas_format

    canvas = {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "inputs": [],
                "widgets_values_named": {
                    "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                    "weight_dtype": "default",
                },
            },
            {
                "id": 2,
                "type": "LoraLoaderModelOnly",
                "inputs": [{"name": "model", "link": 10}],
                "widgets_values_named": {
                    "lora_name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
                    "strength_model": 1.0,
                },
            },
            {
                "id": 3,
                "type": "MiniMaxH3ImageToVideo",
                "inputs": [{"name": "clip", "link": None}],
                "widgets_values_named": {
                    "prompt": "海边日落",
                    "width": 1344,
                    "height": 768,
                    "length": 124,
                },
            },
            {
                "id": 4,
                "type": "BasicGuider",
                "inputs": [
                    {"name": "model", "link": 11},
                    {"name": "conditioning", "link": 12},
                ],
            },
            {
                "id": 5,
                "type": "SaveVideo",
                "inputs": [{"name": "video", "link": None}],
                "widgets_values_named": {"filename_prefix": "video/out"},
            },
            {"id": 99, "type": "MarkdownNote", "inputs": [], "widgets_values_named": {"text": "x"}},
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"],
            [11, 2, 0, 4, 0, "MODEL"],
            [12, 3, 0, 4, 1, "CONDITIONING"],
        ],
    }
    assert is_canvas_format(canvas)
    result = convert_comfy_json(canvas)
    assert result["source"] == "canvas"
    assert "99" not in result["workflow"]  # 注释节点丢弃
    assert result["workflow"]["2"]["class_type"] == "LoraLoaderModelOnly"
    assert result["workflow"]["2"]["inputs"]["model"] == ["1", 0]
    assert result["manifest"]["capability"] == "t2v"  # 无 first_frame
    assert "prompt" in result["manifest"]["inputs"]
    assert result["manifest"]["outputs"]["node"] == "5"
    assert result["manifest"]["accel"]["node"] == "2"


def test_convert_api_endpoint(client: TestClient, auth_header: dict[str, str]) -> None:
    canvas = {
        "nodes": [
            {
                "id": 9,
                "type": "SaveImage",
                "inputs": [],
                "widgets_values_named": {"filename_prefix": "ComfyUI"},
            },
            {
                "id": 6,
                "type": "CLIPTextEncode",
                "inputs": [],
                "widgets_values_named": {"text": "a cat"},
            },
        ],
        "links": [],
    }
    resp = client.post("/api/v1/workflows/convert", json={"data": canvas}, headers=auth_header)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "canvas"
    assert body["node_count"] == 2
    assert "prompt" in body["inputs"] or body["workflow"]["6"]["inputs"]["text"] == "a cat"


def test_qwen_image_21_edit_multi_pack_and_detach() -> None:
    """多参考编辑：4 槽、前两张必填；未上传槽从 TextEncode 断开连线。"""
    from liberastra.providers.comfyui.workflow import _detach_unused_media_links

    pack = get_pack("qwen_image_21_edit_multi")
    assert pack.capability == "i2i"
    assert list(k for k, s in pack.inputs.items() if s.get("type") == "image") == [
        "image",
        "image_2",
        "image_3",
        "image_4",
    ]
    assert pack.inputs["image"]["required"] is True
    assert pack.inputs["image_2"]["required"] is True
    assert pack.inputs["image_3"].get("required") is False
    enc = pack.workflow["5"]["inputs"]
    assert enc["images.image_1"] == ["10", 0]
    assert enc["images.image_4"] == ["13", 0]

    wf = deepcopy(pack.workflow)
    _detach_unused_media_links(wf, pack, {"image": "a.png", "image_2": "b.png"})
    kept = wf["5"]["inputs"]
    assert kept["images.image_1"] == ["10", 0]
    assert kept["images.image_2"] == ["11", 0]
    assert "images.image_3" not in kept
    assert "images.image_4" not in kept


def test_qwen_image_uncensored_lora_accel() -> None:
    """越狱包：默认 UC UNET；LoRA 开/关与视频 accel 同机制。"""
    for name, capability, sampler in (
        ("qwen_image_21_uncensored", "t2i", "7"),
        ("qwen_image_21_edit_uncensored", "i2i", "6"),
        ("qwen_image_21_edit_multi_uncensored", "i2i", "6"),
        ("qwen_image_21_inpaint_uncensored", "i2i", "6"),
    ):
        pack = get_pack(name)
        assert pack.capability == capability
        assert pack.source == "builtin"
        assert pack.accel.get("node") == "200"
        assert pack.accel.get("default_enabled") is True
        assert "UC" in pack.inputs["unet_name"]["default"]
        assert pack.workflow["200"]["class_type"] == "LoraLoaderModelOnly"
        values = {"prompt": "test", "seed": 1}
        if "image" in pack.inputs:
            values["image"] = "uploads/x.png"
        if "image_2" in pack.inputs:
            values["image_2"] = "uploads/y.png"
        if "mask" in pack.inputs:
            values["mask"] = "uploads/m.png"
        off = apply_accel(apply_inputs(pack, values), pack, {"enabled": False}, user_values=values)
        assert "200" not in off
        assert off[sampler]["inputs"]["model"] == ["4", 0]
        on = apply_accel(
            apply_inputs(pack, values),
            pack,
            {
                "enabled": True,
                "lora": "qwen-image-2.1-uncensored-lora.safetensors",
                "strength": 0.85,
            },
            user_values=values,
        )
        assert on["200"]["inputs"]["lora_name"] == "qwen-image-2.1-uncensored-lora.safetensors"
        assert on["200"]["inputs"]["strength_model"] == 0.85
        assert on[sampler]["inputs"]["model"] == ["200", 0]
        validate_pack(pack)

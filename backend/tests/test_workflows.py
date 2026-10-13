"""工作流包加载、参数注入与导入/删除测试。"""

import pytest

from liberastra.providers.base import ProviderError
from liberastra.services.workflows import (
    apply_inputs,
    delete_pack,
    get_pack,
    import_pack,
    list_packs,
)

MINI_WORKFLOW = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 1]}},
    "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m.safetensors"}},
}

MINI_MANIFEST_INPUTS = {
    "prompt": {"node": "1", "field": "inputs.text", "type": "str", "required": True},
    "steps": {"node": "1", "field": "inputs.steps", "type": "int", "default": 20, "min": 1, "max": 50},
}


def test_builtin_pack_loads() -> None:
    packs = list_packs()
    assert any(p.name == "t2i_basic" and p.source == "builtin" for p in packs)
    pack = get_pack("t2i_basic")
    assert pack.capability == "t2i"
    assert "prompt" in pack.inputs


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

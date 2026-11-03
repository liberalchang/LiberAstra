"""原生工具注册表：拼接工具不依赖工作流包或模型。"""

from liberastra.services.native_tools import NATIVE_TOOLS, get_native_tool, tool_specs


def test_registry_has_three_concat_tools() -> None:
    assert [tool.id for tool in NATIVE_TOOLS] == [
        "image_concat",
        "video_concat",
        "audio_concat",
    ]
    assert [tool.media_kind for tool in NATIVE_TOOLS] == ["image", "video", "audio"]
    assert [tool.title for tool in NATIVE_TOOLS] == ["图片拼接", "视频拼接", "音频拼接"]


def test_registry_lookup() -> None:
    tool = get_native_tool("image_concat")
    assert tool is not None
    assert tool.sub_capability == "tool_image_concat"
    assert get_native_tool("missing") is None


def test_tool_specs_are_fixed_native_targets() -> None:
    specs = {spec.target_id: spec for spec in tool_specs()}
    assert set(specs) == {"image_concat", "video_concat", "audio_concat"}
    image = specs["image_concat"]
    assert image.target_type == "tool"
    assert image.sub_capability == "tool_image_concat"
    assert image.provider_type == "native"
    assert image.provider_id is None
    assert image.category == "tool"
    assert image.media_slots == ()

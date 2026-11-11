"""本机原生工具注册表：不依赖工作流包或模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from liberastra.providers.base import ExecutionSpec


@dataclass(frozen=True)
class NativeTool:
    id: str
    title: str
    media_kind: str
    sub_capability: str
    description: str
    page: str
    default_params: dict[str, Any] = field(default_factory=dict)

    def spec(self) -> ExecutionSpec:
        return ExecutionSpec(
            target_type="tool",
            target_id=self.id,
            display_name=self.title,
            sub_capability=self.sub_capability,
            provider_type="native",
            provider_id=None,
            provider_name="本地工具",
            category="tool",
            media_slots=(),
            inputs={},
        )


NATIVE_TOOLS: tuple[NativeTool, ...] = (
    NativeTool(
        id="image_concat",
        title="图片拼接",
        media_kind="image",
        sub_capability="tool_image_concat",
        description="多张图片横排、竖排或网格拼接",
        page="/tools/image-concat",
        default_params={"layout": "horizontal", "columns": 2, "gap": 4, "gap_color": "#FFFFFF"},
    ),
    NativeTool(
        id="video_concat",
        title="视频拼接",
        media_kind="video",
        sub_capability="tool_video_concat",
        description="按顺序拼接多段视频",
        page="/tools/video-concat",
    ),
    NativeTool(
        id="audio_concat",
        title="音频拼接",
        media_kind="audio",
        sub_capability="tool_audio_concat",
        description="按顺序拼接多段音频",
        page="/tools/audio-concat",
    ),
    NativeTool(
        id="audio_extract",
        title="音频提取",
        media_kind="audio",
        sub_capability="tool_audio_extract",
        description="从视频或音频提取完整音轨，或截取固定长度尾音",
        page="",
        default_params={"mode": "tail", "seconds": 5},
    ),
)


def get_native_tool(tool_id: str) -> NativeTool | None:
    for tool in NATIVE_TOOLS:
        if tool.id == tool_id:
            return tool
    return None


def tool_specs() -> list[ExecutionSpec]:
    return [tool.spec() for tool in NATIVE_TOOLS]

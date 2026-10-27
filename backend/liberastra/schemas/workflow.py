"""工作流包响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowPackOut(BaseModel):
    name: str
    capability: str
    description: str
    inputs: dict[str, dict[str, Any]]
    outputs: dict[str, Any]
    source: str
    requirements: dict[str, Any]
    fps: int | None = None  # 视频包帧率；有它前端可按秒设置时长
    accel: dict[str, Any] = Field(default_factory=dict)  # 加速 LoRA 声明；空=无加速能力


class WorkflowImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    capability: str = "t2i"
    description: str = ""
    workflow: dict[str, Any]
    inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    fps: int | None = None
    # None=未传（更新时保留原值）；{}=显式清空；有内容=写入
    accel: dict[str, Any] | None = None
    # 给提示词优化器的技术上下文;None=未传(更新时保留原值)
    llm_note: str | None = None
    overwrite: bool = False


class WorkflowConvertRequest(BaseModel):
    """画布或 API Format JSON → LiberAstra 草稿。"""

    data: dict[str, Any]


class WorkflowConvertOut(BaseModel):
    workflow: dict[str, Any]
    capability: str = "t2i"
    description: str = ""
    inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    fps: int | None = None
    accel: dict[str, Any] = Field(default_factory=dict)
    source: str = "canvas"  # canvas | api
    warnings: list[str] = Field(default_factory=list)
    node_count: int = 0
    node_types: list[str] = Field(default_factory=list)

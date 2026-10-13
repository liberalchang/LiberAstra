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


class WorkflowImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    capability: str = "t2i"
    description: str = ""
    workflow: dict[str, Any]
    inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    overwrite: bool = False

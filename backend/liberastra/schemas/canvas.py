"""画布相关的请求/响应模型。

图结构轻校验：节点/边必须有 id 与类型，data 保持开放（前端演进快，后端不做深校验；
执行时由 canvas_run 按节点类型逐项解析并报错）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

NODE_TYPES = ("input", "function", "concat", "speech")


class CanvasNodeIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["input", "function", "concat", "speech"]
    position: dict[str, float]
    data: dict[str, Any] = Field(default_factory=dict)


class CanvasEdgeIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None


class CanvasGraphIn(BaseModel):
    nodes: list[CanvasNodeIn] = Field(default_factory=list, max_length=200)
    edges: list[CanvasEdgeIn] = Field(default_factory=list, max_length=400)
    viewport: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})


class CanvasCreateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    graph: CanvasGraphIn | None = None


class CanvasUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    graph: CanvasGraphIn | None = None


class CanvasNodeRunOut(BaseModel):
    node_id: str
    status: str
    job_id: str | None
    asset_ids: list[int]
    error: str | None
    published: bool


class CanvasOut(BaseModel):
    id: str
    name: str
    graph: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    node_runs: list[CanvasNodeRunOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CanvasListOut(BaseModel):
    id: str
    name: str
    node_count: int
    created_at: datetime
    updated_at: datetime


class CanvasRunIn(BaseModel):
    """node_ids 为空 = 所有末端分支；force_node_ids 强制重跑（忽略指纹复用）。"""

    node_ids: list[str] = Field(default_factory=list)
    force_node_ids: list[str] = Field(default_factory=list)


class CanvasRunPlanItem(BaseModel):
    node_id: str
    job_id: str | None = None
    status: str
    reused: bool = False


class CanvasRunOut(BaseModel):
    run_id: str
    plan: list[CanvasRunPlanItem]

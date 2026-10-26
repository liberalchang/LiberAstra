"""画布模型：无限画布文档 + 每个节点最近一次执行的记录。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow


class Canvas(Base):
    """一张无限画布：graph 存 React Flow 可序列化的 {nodes, edges, viewport}。"""

    __tablename__ = "canvases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    graph: Mapped[dict] = mapped_column(JSON, default=dict)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    node_runs: Mapped[list[CanvasNodeRun]] = relationship(
        back_populates="canvas", cascade="all, delete-orphan"
    )


class CanvasNodeRun(Base):
    """节点最近一次执行：指纹用于增量复用判定，asset_ids 记录产物。"""

    __tablename__ = "canvas_node_runs"
    __table_args__ = (UniqueConstraint("canvas_id", "node_id", name="uq_canvas_node"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canvas_id: Mapped[str] = mapped_column(
        ForeignKey("canvases.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(16), default="idle")
    asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    canvas: Mapped[Canvas] = relationship(back_populates="node_runs")

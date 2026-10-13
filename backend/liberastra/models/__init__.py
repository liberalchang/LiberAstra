"""SQLAlchemy 模型。所有表保留 owner_id，便于未来扩展多用户。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


from liberastra.models.token import ApiToken  # noqa: E402
from liberastra.models.user import User  # noqa: E402

__all__ = ["ApiToken", "Base", "User", "utcnow"]

"""导演台：会话、消息、技能开关

Revision ID: 0007_agent
Revises: 0006_canvas
Create Date: 2026-11-01

"""

import sqlalchemy as sa
from alembic import op

revision = "0007_agent"
down_revision = "0006_canvas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("canvas_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.Column("active_skill", sa.String(length=64), nullable=False),
        sa.Column("skill_state", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_sessions_owner_id", "agent_sessions", ["owner_id"], unique=False)
    op.create_index("ix_agent_sessions_canvas_id", "agent_sessions", ["canvas_id"], unique=False)
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"], unique=False)

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_messages_session_id", "agent_messages", ["session_id"], unique=False
    )

    op.create_table(
        "agent_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_agent_skill_owner_name"),
    )
    op.create_index("ix_agent_skills_owner_id", "agent_skills", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_skills_owner_id", table_name="agent_skills")
    op.drop_table("agent_skills")
    op.drop_index("ix_agent_messages_session_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_status", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_canvas_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_owner_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")

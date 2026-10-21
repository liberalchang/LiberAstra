"""角色库：characters

Revision ID: 0005_characters
Revises: 0004_app_settings
Create Date: 2026-10-22

"""

import sqlalchemy as sa
from alembic import op

revision = "0005_characters"
down_revision = "0004_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("portrait_path", sa.String(length=512), nullable=True),
        sa.Column("turnaround_path", sa.String(length=512), nullable=True),
        sa.Column("front_path", sa.String(length=512), nullable=True),
        sa.Column("side_path", sa.String(length=512), nullable=True),
        sa.Column("back_path", sa.String(length=512), nullable=True),
        sa.Column("voice_record_id", sa.Integer(), nullable=True),
        sa.Column("voice_name", sa.String(length=256), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voice_record_id"], ["voices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_characters_owner_id", "characters", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_table("characters")

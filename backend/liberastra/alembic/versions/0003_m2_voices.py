"""M2 语音：voices 音色库

Revision ID: 0003_m2_voices
Revises: 0002_m1_foundation
Create Date: 2026-10-13

"""

import sqlalchemy as sa
from alembic import op

revision = "0003_m2_voices"
down_revision = "0002_m1_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("voice_id", sa.String(length=256), nullable=True),
        sa.Column("ref_audio_path", sa.String(length=512), nullable=True),
        sa.Column("ref_text", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voices_provider_id", "voices", ["provider_id"], unique=False)
    op.create_index("ix_voices_owner_id", "voices", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_table("voices")

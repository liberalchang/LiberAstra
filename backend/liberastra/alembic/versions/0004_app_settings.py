"""运行时偏好：app_settings 键值表

Revision ID: 0004_app_settings
Revises: 0003_m2_voices
Create Date: 2026-10-15

"""

import sqlalchemy as sa
from alembic import op

revision = "0004_app_settings"
down_revision = "0003_m2_voices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")

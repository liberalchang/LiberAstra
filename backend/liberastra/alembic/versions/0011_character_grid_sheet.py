"""角色库：9:16 四宫格定妆照

Revision ID: 0011_character_grid_sheet
Revises: 0010_notifications
Create Date: 2026-11-11

"""

import sqlalchemy as sa
from alembic import op

revision = "0011_character_grid_sheet"
down_revision = "0010_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("turnaround_grid_path", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("characters", "turnaround_grid_path")

"""资产来源 origin 与索引，并回填旧数据

Revision ID: 0009_asset_origin
Revises: 0008_job_function
Create Date: 2026-11-06

"""

import sqlalchemy as sa
from alembic import op

revision = "0009_asset_origin"
down_revision = "0008_job_function"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("origin", sa.String(length=16), nullable=False, server_default="output"),
    )
    op.create_index("ix_assets_origin", "assets", ["origin"], unique=False)
    op.execute(
        sa.text(
            """
            UPDATE assets SET origin = 'character'
            WHERE json_extract(meta, '$.character_id') IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE assets SET origin = 'canvas'
            WHERE origin = 'output'
              AND (
                json_extract(meta, '$.canvas_temp') IS NOT NULL
                OR json_extract(meta, '$.canvas_mask') IS NOT NULL
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE assets SET origin = CASE WHEN hidden = 1 THEN 'canvas' ELSE 'upload' END
            WHERE origin = 'output'
              AND json_extract(meta, '$.source') = 'canvas-upload'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_assets_origin", table_name="assets")
    op.drop_column("assets", "origin")

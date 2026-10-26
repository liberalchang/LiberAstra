"""无限画布：canvases + canvas_node_runs,assets 增加 hidden 标记

Revision ID: 0006_canvas
Revises: 0005_characters
Create Date: 2026-10-26

"""

import sqlalchemy as sa
from alembic import op

revision = "0006_canvas"
down_revision = "0005_characters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canvases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_canvases_owner_id", "canvases", ["owner_id"], unique=False)

    op.create_table(
        "canvas_node_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canvas_id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canvas_id"], ["canvases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canvas_id", "node_id", name="uq_canvas_node"),
    )
    op.create_index(
        "ix_canvas_node_runs_canvas_id", "canvas_node_runs", ["canvas_id"], unique=False
    )

    op.add_column(
        "assets",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_assets_hidden", "assets", ["hidden"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assets_hidden", table_name="assets")
    op.drop_column("assets", "hidden")
    op.drop_table("canvas_node_runs")
    op.drop_table("canvases")

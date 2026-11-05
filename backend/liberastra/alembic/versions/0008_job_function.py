"""任务功能标识与素材查询索引

Revision ID: 0008_job_function
Revises: 0007_agent
Create Date: 2026-11-05

"""

import sqlalchemy as sa
from alembic import op

revision = "0008_job_function"
down_revision = "0007_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("function", sa.String(length=64), nullable=True))
    op.execute(sa.text('UPDATE jobs SET "function" = kind WHERE "function" IS NULL'))
    op.create_index("ix_jobs_function", "jobs", ["function"], unique=False)
    op.create_index(
        "ix_assets_owner_hidden_kind_created",
        "assets",
        ["owner_id", "hidden", "kind", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assets_owner_hidden_kind_created", table_name="assets")
    op.drop_index("ix_jobs_function", table_name="jobs")
    op.drop_column("jobs", "function")

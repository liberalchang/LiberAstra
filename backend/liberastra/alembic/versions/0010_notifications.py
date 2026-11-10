"""通知渠道、规则和投递 outbox

Revision ID: 0010_notifications
Revises: 0009_asset_origin
Create Date: 2026-11-10

"""

import sqlalchemy as sa
from alembic import op

revision = "0010_notifications"
down_revision = "0009_asset_origin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("backoff_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "name", name="uq_notification_channels_owner_name"
        ),
    )
    op.create_index(
        "ix_notification_channels_owner_id",
        "notification_channels",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_channels_type", "notification_channels", ["type"], unique=False
    )

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled_since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("progress_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("job_kinds", sa.JSON(), nullable=False),
        sa.Column("max_jobs_per_digest", sa.Integer(), nullable=False),
        sa.Column("quiet_hours", sa.JSON(), nullable=True),
        sa.Column("include_outputs", sa.Boolean(), nullable=False),
        sa.Column("template_succeeded", sa.Text(), nullable=True),
        sa.Column("template_failed", sa.Text(), nullable=True),
        sa.Column("template_progress", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_notification_rules_owner_name"),
    )
    op.create_index(
        "ix_notification_rules_owner_id", "notification_rules", ["owner_id"], unique=False
    )

    op.create_table(
        "notification_rule_channels",
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["notification_channels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["notification_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id", "channel_id"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["notification_channels.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["notification_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_deliveries_owner_id",
        "notification_deliveries",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_job_id",
        "notification_deliveries",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_dedup_key",
        "notification_deliveries",
        ["dedup_key"],
        unique=True,
    )
    op.create_index(
        "ix_notification_deliveries_status",
        "notification_deliveries",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_claim",
        "notification_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_rule_channels")
    op.drop_table("notification_rules")
    op.drop_table("notification_channels")

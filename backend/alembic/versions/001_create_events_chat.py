"""create events and chat tables

Revision ID: 001_create_events_chat
Revises:
Create Date: 2026-07-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

revision = "001_create_events_chat"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("heat", sa.Float(), nullable=True, server_default="0"),
        sa.Column("report_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("time_start", sa.DateTime(), nullable=True),
        sa.Column("time_end", sa.DateTime(), nullable=True),
        sa.Column("positive", sa.Float(), nullable=True, server_default="0"),
        sa.Column("neutral", sa.Float(), nullable=True, server_default="0"),
        sa.Column("negative", sa.Float(), nullable=True, server_default="0"),
        sa.Column("stage", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="0"),
        sa.Column("prob_latent", sa.Float(), nullable=True, server_default="0"),
        sa.Column("prob_growth", sa.Float(), nullable=True, server_default="0"),
        sa.Column("prob_peak", sa.Float(), nullable=True, server_default="0"),
        sa.Column("prob_decline", sa.Float(), nullable=True, server_default="0"),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("sources", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_events_heat", "events", ["heat"])
    op.create_index("idx_events_time_start", "events", ["time_start"])
    op.create_index("idx_events_stage", "events", ["stage"])

    op.create_table(
        "event_trend_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_predicted", sa.SmallInteger(), nullable=True, server_default="0"),
        sa.Column("predict_heat", sa.Float(), nullable=True),
        sa.Column("predict_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "date", "is_predicted", name="uq_event_trend"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_trend_event_date", "event_trend_daily", ["event_id", "date"])

    op.create_table(
        "event_keywords",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("word", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=True, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "word", name="uq_event_keyword"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_keyword_event_rank", "event_keywords", ["event_id", "rank"])

    op.create_table(
        "event_platforms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("platform_name", sa.String(50), nullable=False),
        sa.Column("ratio", sa.Float(), nullable=True, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=True, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "platform_name", name="uq_event_platform"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_platform_event_rank", "event_platforms", ["event_id", "rank"])

    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_conv_user", "conversations", ["user_id"])
    op.create_index("idx_conv_event", "conversations", ["event_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_msg_conv_time", "messages", ["conversation_id", "created_at"])

    op.create_foreign_key("fk_trend_event", "event_trend_daily", "events", ["event_id"], ["event_id"])
    op.create_foreign_key("fk_keyword_event", "event_keywords", "events", ["event_id"], ["event_id"])
    op.create_foreign_key("fk_platform_event", "event_platforms", "events", ["event_id"], ["event_id"])
    op.create_foreign_key("fk_conv_user", "conversations", "users", ["user_id"], ["id"])
    op.create_foreign_key("fk_msg_conv", "messages", "conversations", ["conversation_id"], ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("event_platforms")
    op.drop_table("event_keywords")
    op.drop_table("event_trend_daily")
    op.drop_table("events")

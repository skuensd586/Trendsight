"""add risk_level and event_time to events

Revision ID: 002_add_event_fields
Revises: 001_create_events_chat
Create Date: 2026-07-09 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "002_add_event_fields"
down_revision = "001_create_events_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("risk_level", sa.String(20), nullable=True))
    op.add_column("events", sa.Column("event_time", sa.DateTime(), nullable=True))
    op.create_index("idx_events_risk_level", "events", ["risk_level"])


def downgrade() -> None:
    op.drop_index("idx_events_risk_level", table_name="events")
    op.drop_column("events", "risk_level")
    op.drop_column("events", "event_time")

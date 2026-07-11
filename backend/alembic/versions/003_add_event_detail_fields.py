"""add summary, location, cause, people to events

Revision ID: 003_add_event_detail_fields
Revises: 002_add_event_fields
Create Date: 2026-07-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

# revision identifiers, used by Alembic.
revision: str = "003_add_event_detail_fields"
down_revision: Union[str, Sequence[str], None] = "002_add_event_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add event detail fields for frontend display."""
    op.add_column("events", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("location", sa.String(200), nullable=True))
    op.add_column("events", sa.Column("cause", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("people", JSON(), nullable=True))


def downgrade() -> None:
    """Remove event detail fields."""
    op.drop_column("events", "people")
    op.drop_column("events", "cause")
    op.drop_column("events", "location")
    op.drop_column("events", "summary")

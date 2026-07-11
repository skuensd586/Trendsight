"""add authenticity JSON column to events

Revision ID: 003_add_authenticity
Revises: 002_add_event_fields
Create Date: 2026-07-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "003_add_authenticity"
down_revision: Union[str, Sequence[str], None] = "002_add_event_fields"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "authenticity",
            JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "events",
        "authenticity",
    )
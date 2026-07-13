"""add propagation JSON column to events

Revision ID: 004_add_propagation
Revises: 00ac0cbdc0a8
Create Date: 2026-07-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "004_add_propagation"
down_revision: Union[str, Sequence[str], None] = "00ac0cbdc0a8"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "propagation",
            JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "events",
        "propagation",
    )

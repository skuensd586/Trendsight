"""merge authenticity and event detail fields

Revision ID: 00ac0cbdc0a8
Revises: 003_add_authenticity, 003_add_event_detail_fields
Create Date: 2026-07-11 13:15:56.086093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00ac0cbdc0a8'
down_revision: Union[str, Sequence[str], None] = ('003_add_authenticity', '003_add_event_detail_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

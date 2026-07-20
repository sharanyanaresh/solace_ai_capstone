"""initial schema

Revision ID: 31711a0e0b21
Revises: 
Create Date: 2026-07-05 00:39:19.951577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31711a0e0b21'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the full initial schema from the ORM models (single source of truth)."""
    from backend.app.db import Base
    from backend.app import models  # noqa: F401 — register all mappers

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop all tables."""
    from backend.app.db import Base
    from backend.app import models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind())

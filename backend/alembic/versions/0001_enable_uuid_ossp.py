"""Enable uuid-ossp extension.

Revision ID: 0001_enable_uuid_ossp
Revises: None
Create Date: 2026-05-10 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_uuid_ossp"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')

"""Add document virus scan status.

Revision ID: 0024_add_document_scan_status
Revises: 0023_create_notification_deliveries
Create Date: 2026-05-10 07:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024_add_document_scan_status"
down_revision: str | None = "0023_create_notification_deliveries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOCUMENT_SCAN_STATUSES = ("pending", "clean", "infected", "failed")


def upgrade() -> None:
    scan_status = postgresql.ENUM(*DOCUMENT_SCAN_STATUSES, name="document_scan_status")
    scan_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "scan_status",
            postgresql.ENUM(
                *DOCUMENT_SCAN_STATUSES,
                name="document_scan_status",
                create_type=False,
            ),
            server_default="clean",
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("scan_result", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_scan_status", "documents", ["scan_status"])


def downgrade() -> None:
    op.drop_index("ix_documents_scan_status", table_name="documents")
    op.drop_column("documents", "scanned_at")
    op.drop_column("documents", "scan_result")
    op.drop_column("documents", "scan_status")
    postgresql.ENUM(name="document_scan_status").drop(op.get_bind(), checkfirst=True)

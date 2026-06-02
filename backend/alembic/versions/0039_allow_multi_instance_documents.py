"""allow multi instance documents

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-02
"""

import sqlalchemy as sa

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_latest_per_group")
    op.execute(
        """
        UPDATE documents
        SET is_latest = true,
            updated_at = now()
        WHERE is_deleted IS false
          AND (
            doc_type IN ('payment_voucher', 'supplier_quote')
            OR (doc_type = 'acceptance_report' AND acceptance_step_id IS NOT NULL)
          )
        """,
    )
    op.execute(
        """
        UPDATE phases
        SET status = 'in_progress',
            enter_at = COALESCE(enter_at, now()),
            updated_at = now()
        WHERE phase_no = 6
          AND status = 'waiting'
        """,
    )


def downgrade() -> None:
    op.create_index(
        "uq_documents_latest_per_group",
        "documents",
        ["sub_project_id", "phase_id", "doc_type"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
    )

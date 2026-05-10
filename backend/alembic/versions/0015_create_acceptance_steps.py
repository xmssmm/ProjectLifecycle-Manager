"""Create acceptance step table.

Revision ID: 0015_create_acceptance_steps
Revises: 0014_create_payments
Create Date: 2026-05-11 01:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_create_acceptance_steps"
down_revision: str | None = "0014_create_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCEPTANCE_STEP_STATUSES = ("not_started", "in_progress", "completed")


def upgrade() -> None:
    acceptance_step_status = postgresql.ENUM(
        *ACCEPTANCE_STEP_STATUSES,
        name="acceptance_step_status",
    )
    acceptance_step_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "acceptance_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=120), nullable=False),
        sa.Column("responsible_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *ACCEPTANCE_STEP_STATUSES,
                name="acceptance_step_status",
                create_type=False,
            ),
            server_default="not_started",
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsible_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phase_id", "step_no", name="uq_acceptance_steps_phase_step_no"),
    )
    op.create_index("ix_acceptance_steps_phase_id", "acceptance_steps", ["phase_id"])
    op.create_index(
        "ix_acceptance_steps_responsible_id",
        "acceptance_steps",
        ["responsible_id"],
    )
    op.create_index("ix_acceptance_steps_status", "acceptance_steps", ["status"])
    op.create_foreign_key(
        "fk_documents_acceptance_step_id_acceptance_steps",
        "documents",
        "acceptance_steps",
        ["acceptance_step_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_acceptance_step_id_acceptance_steps",
        "documents",
        type_="foreignkey",
    )
    op.drop_index("ix_acceptance_steps_status", table_name="acceptance_steps")
    op.drop_index("ix_acceptance_steps_responsible_id", table_name="acceptance_steps")
    op.drop_index("ix_acceptance_steps_phase_id", table_name="acceptance_steps")
    op.drop_table("acceptance_steps")
    postgresql.ENUM(name="acceptance_step_status").drop(op.get_bind(), checkfirst=True)

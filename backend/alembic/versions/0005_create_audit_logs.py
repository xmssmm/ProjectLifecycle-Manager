"""Create partitioned audit logs table.

Revision ID: 0005_create_audit_logs
Revises: 0004_create_notifications
Create Date: 2026-05-10 20:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_create_audit_logs"
down_revision: str | None = "0004_create_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_logs (
            id uuid DEFAULT uuid_generate_v4() NOT NULL,
            actor_id uuid NULL,
            action varchar(128) NOT NULL,
            target_type varchar(64) NOT NULL,
            target_id varchar(128) NOT NULL,
            before_state jsonb DEFAULT '{}'::jsonb NOT NULL,
            after_state jsonb DEFAULT '{}'::jsonb NOT NULL,
            ip_address varchar(45) NULL,
            user_agent varchar(512) NULL,
            extra jsonb DEFAULT '{}'::jsonb NOT NULL,
            request_id varchar(64) NULL,
            created_at timestamptz DEFAULT now() NOT NULL,
            updated_at timestamptz DEFAULT now() NOT NULL,
            CONSTRAINT pk_audit_logs PRIMARY KEY (id, created_at),
            CONSTRAINT fk_audit_logs_actor_id_users
                FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL
        ) PARTITION BY RANGE (created_at)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_audit_logs_actor_created
        ON audit_logs (actor_id, created_at)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_audit_logs_action_created
        ON audit_logs (action, created_at)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_audit_logs_target_created
        ON audit_logs (target_type, target_id, created_at)
        """,
    )
    op.execute("CREATE INDEX ix_audit_logs_request_id ON audit_logs (request_id)")
    op.execute(
        """
        DO $$
        DECLARE
            base_month date := date_trunc('month', now())::date;
            partition_start date;
            partition_end date;
            partition_name text;
        BEGIN
            FOR month_offset IN 0..12 LOOP
                partition_start := (base_month + (month_offset || ' months')::interval)::date;
                partition_end := (base_month + ((month_offset + 1) || ' months')::interval)::date;
                partition_name := 'audit_logs_' || to_char(partition_start, 'YYYYMM');
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs '
                    || 'FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    partition_start,
                    partition_end
                );
            END LOOP;
        END $$;
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")

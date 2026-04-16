"""outbox retry and dead letter fields

Revision ID: 0003_outbox_retry_deadletter
Revises: 0002_outbox_events
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_outbox_retry_deadletter"
down_revision = "0002_outbox_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("outbox_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("outbox_events", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_column("outbox_events", "next_attempt_at")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "attempts")

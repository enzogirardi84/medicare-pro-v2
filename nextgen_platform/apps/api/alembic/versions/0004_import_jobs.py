"""add import jobs

Revision ID: 0004_import_jobs
Revises: 0003_outbox_retry_deadletter
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_import_jobs"
down_revision = "0003_outbox_retry_deadletter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rows_valid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("task_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_tenant_created", "import_jobs", ["tenant_id", "created_at"], unique=False)
    op.alter_column("import_jobs", "rows_valid", server_default=None)
    op.alter_column("import_jobs", "rows_inserted", server_default=None)
    op.alter_column("import_jobs", "errors_json", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_import_jobs_tenant_created", table_name="import_jobs")
    op.drop_table("import_jobs")

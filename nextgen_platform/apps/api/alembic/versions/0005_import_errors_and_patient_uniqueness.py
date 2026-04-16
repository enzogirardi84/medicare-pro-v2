"""import job errors and unique patient documents

Revision ID: 0005_import_errors_and_patient_uniqueness
Revises: 0004_import_jobs
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_import_errors_and_patient_uniqueness"
down_revision = "0004_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_jobs", sa.Column("source_csv_text", sa.Text(), nullable=True))

    op.create_table(
        "import_job_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_job_errors_job", "import_job_errors", ["import_job_id"], unique=False)
    op.alter_column("import_job_errors", "line_number", server_default=None)

    # Normaliza duplicados preexistentes para poder garantizar unicidad por tenant+documento.
    op.execute(
        """
        DELETE FROM patients p
        USING patients p2
        WHERE p.tenant_id = p2.tenant_id
          AND p.document_number = p2.document_number
          AND p.ctid > p2.ctid
        """
    )
    op.create_index("ux_patients_tenant_doc_unique", "patients", ["tenant_id", "document_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_patients_tenant_doc_unique", table_name="patients")
    op.drop_index("ix_import_job_errors_job", table_name="import_job_errors")
    op.drop_table("import_job_errors")
    op.drop_column("import_jobs", "source_csv_text")

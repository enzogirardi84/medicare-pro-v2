"""add read path indexes for patients and visits

Revision ID: 0006_read_path_indexes
Revises: 0005_import_errors_and_patient_uniqueness
Create Date: 2026-04-16
"""

from alembic import op

revision = "0006_read_path_indexes"
down_revision = "0005_import_errors_and_patient_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Optimiza listados por tenant ordenados por fecha descendente.
    op.create_index(
        "ix_patients_tenant_created_desc",
        "patients",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_visits_tenant_created_desc",
        "visits",
        ["tenant_id", "created_at"],
        unique=False,
    )

    # Optimiza visitas filtradas por paciente + orden por fecha.
    op.create_index(
        "ix_visits_tenant_patient_created_desc",
        "visits",
        ["tenant_id", "patient_id", "created_at"],
        unique=False,
    )

    # Acelera búsquedas ILIKE en full_name para pacientes.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_patients_full_name_trgm ON patients USING gin (full_name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_patients_full_name_trgm")
    op.drop_index("ix_visits_tenant_patient_created_desc", table_name="visits")
    op.drop_index("ix_visits_tenant_created_desc", table_name="visits")
    op.drop_index("ix_patients_tenant_created_desc", table_name="patients")

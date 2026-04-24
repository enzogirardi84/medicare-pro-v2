"""
Seed Initial Data

Datos iniciales para el sistema.

Revision ID: 000000000001
Revises: 000000000000
Create Date: 2024-01-15 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '000000000001'
down_revision = '000000000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Insertar datos iniciales necesarios para el funcionamiento del sistema.
    """
    
    # Tabla: users (datos de ejemplo - cambiar en producción)
    users_table = table(
        'users',
        column('id', postgresql.UUID),
        column('email', sa.String),
        column('password_hash', sa.String),
        column('nombre', sa.String),
        column('rol', sa.String),
        column('matricula', sa.String),
        column('empresa', sa.String),
        column('activo', sa.Boolean),
    )
    
    # Nota: En producción, usar password hash real generado con bcrypt
    op.bulk_insert(users_table, [
        {
            'id': '00000000-0000-0000-0000-000000000001',
            'email': 'admin@medicare.local',
            'password_hash': '$2b$12$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # Placeholder
            'nombre': 'Administrador del Sistema',
            'rol': 'admin',
            'matricula': 'ADMIN-001',
            'empresa': 'Medicare Pro',
            'activo': True,
        },
    ])
    
    # Insertar roles/perfiles de ejemplo
    # (En un sistema real, esto vendría de una tabla de roles)


def downgrade() -> None:
    """
    Limpiar datos de seed.
    """
    op.execute("DELETE FROM users WHERE email = 'admin@medicare.local'")

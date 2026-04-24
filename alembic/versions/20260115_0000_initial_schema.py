"""
Initial Schema

Revision inicial con tablas core del sistema.

Revision ID: 000000000000
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '000000000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Tabla: users ###
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('rol', sa.String(50), nullable=False),
        sa.Column('matricula', sa.String(50), nullable=True),
        sa.Column('empresa', sa.String(255), nullable=False),
        sa.Column('activo', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_empresa', 'users', ['empresa'])
    
    # ### Tabla: pacientes ###
    op.create_table(
        'pacientes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dni', sa.String(20), unique=True, nullable=False, index=True),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('apellido', sa.String(255), nullable=False),
        sa.Column('fecha_nacimiento', sa.Date(), nullable=True),
        sa.Column('sexo', sa.String(1), nullable=True),
        sa.Column('telefono', sa.String(50), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('direccion', sa.Text(), nullable=True),
        sa.Column('obra_social', sa.String(255), nullable=True),
        sa.Column('numero_afiliado', sa.String(100), nullable=True),
        sa.Column('alergias', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('medicamentos_actuales', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('empresa', sa.String(255), nullable=False),
        sa.Column('activo', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_pacientes_dni', 'pacientes', ['dni'])
    op.create_index('ix_pacientes_empresa', 'pacientes', ['empresa'])
    op.create_index('ix_pacientes_nombre', 'pacientes', ['nombre', 'apellido'])
    
    # ### Tabla: evoluciones ###
    op.create_table(
        'evoluciones',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('paciente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pacientes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('medico_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
        sa.Column('nota', sa.Text(), nullable=False),
        sa.Column('diagnostico', sa.Text(), nullable=True),
        sa.Column('tratamiento', sa.Text(), nullable=True),
        sa.Column('proxima_cita', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_evoluciones_paciente_id', 'evoluciones', ['paciente_id'])
    op.create_index('ix_evoluciones_fecha', 'evoluciones', ['fecha'])
    op.create_index('ix_evoluciones_medico_id', 'evoluciones', ['medico_id'])
    
    # ### Tabla: signos_vitales ###
    op.create_table(
        'signos_vitales',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('paciente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pacientes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('profesional_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
        sa.Column('presion_arterial', sa.String(20), nullable=True),
        sa.Column('frecuencia_cardiaca', sa.Integer(), nullable=True),
        sa.Column('frecuencia_respiratoria', sa.Integer(), nullable=True),
        sa.Column('temperatura', sa.Numeric(4, 2), nullable=True),
        sa.Column('saturacion_o2', sa.Integer(), nullable=True),
        sa.Column('peso', sa.Numeric(5, 2), nullable=True),
        sa.Column('talla', sa.Numeric(4, 2), nullable=True),
        sa.Column('glucemia', sa.Numeric(5, 2), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_vitales_paciente_id', 'signos_vitales', ['paciente_id'])
    op.create_index('ix_vitales_fecha', 'signos_vitales', ['fecha'])
    
    # ### Tabla: recetas ###
    op.create_table(
        'recetas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('paciente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pacientes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('medico_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('vigencia_dias', sa.Integer(), default=30),
        sa.Column('activa', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_recetas_paciente_id', 'recetas', ['paciente_id'])
    op.create_index('ix_recetas_medico_id', 'recetas', ['medico_id'])
    op.create_index('ix_recetas_fecha', 'recetas', ['fecha'])
    
    # ### Tabla: medicamentos_receta ###
    op.create_table(
        'medicamentos_receta',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('receta_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recetas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('dosis', sa.String(100), nullable=False),
        sa.Column('frecuencia', sa.String(100), nullable=False),
        sa.Column('duracion', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # ### Tabla: estudios ###
    op.create_table(
        'estudios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('paciente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pacientes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),  # laboratorio, imagen, otros
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('fecha_solicitud', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fecha_resultado', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resultado', sa.Text(), nullable=True),
        sa.Column('archivo_url', sa.String(500), nullable=True),
        sa.Column('estado', sa.String(20), default='pendiente'),  # pendiente, completado, cancelado
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_estudios_paciente_id', 'estudios', ['paciente_id'])
    op.create_index('ix_estudios_tipo', 'estudios', ['tipo'])
    op.create_index('ix_estudios_estado', 'estudios', ['estado'])
    
    # ### Tabla: audit_log (append-only) ###
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_category', sa.String(50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('user_empresa', sa.String(255), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('previous_hash', sa.String(64), nullable=False),
        sa.Column('entry_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('signature', sa.String(128), nullable=False),
    )
    op.create_index('ix_audit_timestamp', 'audit_log', ['timestamp'])
    op.create_index('ix_audit_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_resource', 'audit_log', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_event_type', 'audit_log', ['event_type'])
    
    # Restricción: audit_log es append-only (no updates, no deletes)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log es append-only: no se permiten modificaciones';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)
    
    op.execute("""
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)


def downgrade() -> None:
    # Eliminar en orden inverso (respetando FKs)
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification()")
    
    op.drop_table('audit_log')
    op.drop_table('medicamentos_receta')
    op.drop_table('recetas')
    op.drop_table('estudios')
    op.drop_table('signos_vitales')
    op.drop_table('evoluciones')
    op.drop_table('pacientes')
    op.drop_table('users')

"""
Script de utilidad para manejar migraciones de base de datos.

Uso:
    # Crear nueva migración
    python scripts/db_migrate.py revision -m "descripcion"
    
    # Aplicar migraciones
    python scripts/db_migrate.py upgrade
    
    # Rollback última migración
    python scripts/db_migrate.py downgrade -1
    
    # Ver estado actual
    python scripts/db_migrate.py current
    
    # Historial
    python scripts/db_migrate.py history
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_alembic_command(command: list[str]) -> int:
    """Ejecuta comando alembic."""
    alembic_ini = Path(__file__).parent.parent / "alembic" / "alembic.ini"
    
    if not alembic_ini.exists():
        print(f"Error: No se encontró {alembic_ini}")
        print("Asegúrate de estar en el directorio raíz del proyecto")
        return 1
    
    cmd = ["alembic", "-c", str(alembic_ini)] + command
    
    print(f"Ejecutando: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


def create_revision(message: str, autogenerate: bool = False) -> int:
    """Crea nueva migración."""
    cmd = ["revision", "-m", message]
    if autogenerate:
        cmd.append("--autogenerate")
    
    return run_alembic_command(cmd)


def upgrade(revision: str = "head") -> int:
    """Aplica migraciones hasta revisión especificada."""
    return run_alembic_command(["upgrade", revision])


def downgrade(revision: str) -> int:
    """Rollback a revisión especificada."""
    return run_alembic_command(["downgrade", revision])


def current() -> int:
    """Muestra revisión actual."""
    return run_alembic_command(["current"])


def history() -> int:
    """Muestra historial de migraciones."""
    return run_alembic_command(["history", "--verbose"])


def check() -> int:
    """Verifica estado de migraciones."""
    print("Verificando estado de migraciones...")
    
    # Verificar conexión
    result = run_alembic_command(["current"])
    if result != 0:
        print("Error: No se pudo conectar a la base de datos")
        return result
    
    # Verificar si hay migraciones pendientes
    print("\nVerificando migraciones pendientes...")
    result = run_alembic_command(["check"])
    
    return result


def validate_env() -> bool:
    """Valida que las variables de entorno necesarias estén configuradas."""
    required = ["DATABASE_URL"]
    
    missing = []
    for var in required:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"Error: Variables de entorno faltantes: {', '.join(missing)}")
        print("\nAsegúrate de configurar:")
        print("  export DATABASE_URL=postgresql://user:pass@host:port/dbname")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Utilidad de migraciones de base de datos para Medicare Pro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s revision -m "agregar tabla pacientes"
  %(prog)s revision -m "cambios en evoluciones" --autogenerate
  %(prog)s upgrade
  %(prog)s downgrade -1
  %(prog)s current
  %(prog)s history
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")
    
    # revision
    revision_parser = subparsers.add_parser("revision", help="Crear nueva migración")
    revision_parser.add_argument("-m", "--message", required=True, help="Descripción de la migración")
    revision_parser.add_argument("--autogenerate", action="store_true", help="Autogenerar desde modelos")
    
    # upgrade
    upgrade_parser = subparsers.add_parser("upgrade", help="Aplicar migraciones")
    upgrade_parser.add_argument("revision", nargs="?", default="head", help="Revisión destino (default: head)")
    
    # downgrade
    downgrade_parser = subparsers.add_parser("downgrade", help="Rollback de migraciones")
    downgrade_parser.add_argument("revision", help="Revisión destino (ej: -1, base, revision_id)")
    
    # current
    subparsers.add_parser("current", help="Mostrar revisión actual")
    
    # history
    subparsers.add_parser("history", help="Mostrar historial de migraciones")
    
    # check
    subparsers.add_parser("check", help="Verificar estado de migraciones")
    
    # validate
    subparsers.add_parser("validate", help="Validar configuración de entorno")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Validar entorno (excepto para validate)
    if args.command != "validate":
        if not validate_env():
            return 1
    
    # Ejecutar comando
    if args.command == "revision":
        return create_revision(args.message, args.autogenerate)
    elif args.command == "upgrade":
        return upgrade(args.revision)
    elif args.command == "downgrade":
        return downgrade(args.revision)
    elif args.command == "current":
        return current()
    elif args.command == "history":
        return history()
    elif args.command == "check":
        return check()
    elif args.command == "validate":
        if validate_env():
            print("✓ Configuración de entorno válida")
            return 0
        return 1
    
    return 1


if __name__ == "__main__":
    sys.exit(main())

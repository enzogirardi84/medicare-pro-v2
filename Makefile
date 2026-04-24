# Makefile para Medicare Pro
# Comandos comunes para desarrollo, testing y deployment

.PHONY: help install dev test lint format clean docker-up docker-down migrate docs

# Colores para output
BLUE=\033[36m
GREEN=\033[32m
YELLOW=\033[33m
RED=\033[31m
NC=\033[0m # No Color

help: ## Muestra esta ayuda
	@echo "${BLUE}Medicare Pro - Comandos disponibles:${NC}"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  ${YELLOW}%-20s${NC} %s\n", $$1, $$2}'

# ============================================================
# INSTALACIÓN Y DEPENDENCIAS
# ============================================================

install: ## Instala dependencias de producción
	@echo "${BLUE}Instalando dependencias...${NC}"
	pip install -r requirements.txt

install-dev: ## Instala dependencias de desarrollo
	@echo "${BLUE}Instalando dependencias de desarrollo...${NC}"
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# ============================================================
# DESARROLLO
# ============================================================

dev: ## Inicia la aplicación en modo desarrollo
	@echo "${GREEN}Iniciando Medicare Pro (modo desarrollo)...${NC}"
	streamlit run main.py

dev-docker: ## Inicia entorno completo con Docker Compose
	@echo "${GREEN}Iniciando stack completo con Docker...${NC}"
	docker-compose up -d

stop-docker: ## Detiene los contenedores Docker
	@echo "${YELLOW}Deteniendo contenedores...${NC}"
	docker-compose down

logs: ## Muestra logs de los servicios Docker
	docker-compose logs -f

# ============================================================
# TESTING
# ============================================================

test: ## Ejecuta todos los tests
	@echo "${BLUE}Ejecutando tests...${NC}"
	pytest tests/ -v --tb=short

test-coverage: ## Ejecuta tests con cobertura
	@echo "${BLUE}Ejecutando tests con cobertura...${NC}"
	pytest tests/ -v --cov=core --cov=views --cov-report=html --cov-report=term

test-unit: ## Ejecuta solo tests unitarios
	@echo "${BLUE}Ejecutando tests unitarios...${NC}"
	pytest tests/test_*.py -v -k "not integration"

test-integration: ## Ejecuta tests de integración
	@echo "${BLUE}Ejecutando tests de integración...${NC}"
	pytest tests/test_integration_*.py -v

test-e2e: ## Ejecuta tests E2E con Playwright
	@echo "${BLUE}Ejecutando tests E2E...${NC}"
	pytest tests/e2e/ -v

# ============================================================
# CALIDAD DE CÓDIGO
# ============================================================

lint: ## Ejecuta linters (ruff, mypy)
	@echo "${BLUE}Ejecutando linters...${NC}"
	ruff check core/ views/ tests/
	mypy core/ --ignore-missing-imports

format: ## Formatea el código (black, isort)
	@echo "${BLUE}Formateando código...${NC}"
	black core/ views/ tests/
	isort core/ views/ tests/

format-check: ## Verifica formato sin modificar
	@echo "${BLUE}Verificando formato...${NC}"
	black --check core/ views/ tests/
	isort --check-only core/ views/ tests/

security-check: ## Ejecuta análisis de seguridad
	@echo "${BLUE}Análisis de seguridad...${NC}"
	bandit -r core/ views/ -f json -o bandit-report.json || true
	safety check -r requirements.txt

# ============================================================
# BASE DE DATOS
# ============================================================

db-migrate: ## Ejecuta migraciones de base de datos
	@echo "${BLUE}Ejecutando migraciones...${NC}"
	python scripts/db_migrate.py upgrade

db-rollback: ## Rollback de última migración
	@echo "${YELLOW}Haciendo rollback de migración...${NC}"
	python scripts/db_migrate.py downgrade -1

db-reset: ## Reset completo de base de datos (¡Cuidado!)
	@echo "${RED}⚠️  Resetear base de datos...${NC}"
	@read -p "¿Estás seguro? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "Reseteando..."; \
		python scripts/db_migrate.py downgrade base; \
	else \
		echo "Cancelado."; \
	fi

db-seed: ## Carga datos iniciales (seeds)
	@echo "${BLUE}Cargando datos iniciales...${NC}"
	python scripts/db_migrate.py upgrade

# ============================================================
# DOCUMENTACIÓN
# ============================================================

docs: ## Genera documentación
	@echo "${BLUE}Generando documentación...${NC}"
	@echo "Documentación disponible en docs/"

docs-api: ## Abre documentación de API
	@echo "${GREEN}Documentación API:${NC}"
	@echo "Local: http://localhost:8000/docs"
	@echo "OpenAPI Spec: api/openapi.yaml"

# ============================================================
# LIMPIEZA
# ============================================================

clean: ## Limpia archivos temporales
	@echo "${YELLOW}Limpiando archivos temporales...${NC}"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ .coverage htmlcov/ dist/ build/
	rm -f bandit-report.json

clean-docker: ## Limpia contenedores y volúmenes Docker
	@echo "${RED}Limpiando Docker...${NC}"
	docker-compose down -v
	docker system prune -f

# ============================================================
# UTILIDADES
# ============================================================

shell: ## Abre shell de Python con contexto de la app
	@echo "${GREEN}Abriendo shell...${NC}"
	python -c "import streamlit as st; from core.database import *; print('Contexto cargado')"

health: ## Verifica salud del sistema
	@echo "${BLUE}Verificando salud del sistema...${NC}"
	@python -c "
import sys
try:
    import streamlit
    import pandas
    import numpy
    print('✅ Dependencias principales OK')
except ImportError as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

pre-commit: ## Instala y ejecuta pre-commit hooks
	@echo "${BLUE}Configurando pre-commit...${NC}"
	cp scripts/pre-commit-check.sh .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "${GREEN}Pre-commit hook instalado${NC}"

# ============================================================
# DEPLOYMENT
# ============================================================

build: ## Construye imagen Docker
	@echo "${BLUE}Construyendo imagen Docker...${NC}"
	docker build -t medicare-pro:latest .

push: ## Push a registro Docker (requiere login)
	@echo "${BLUE}Push a registro...${NC}"
	docker push medicare-pro:latest

# ============================================================
# INFO
# ============================================================

info: ## Muestra información del proyecto
	@echo "${GREEN}Medicare Pro${NC}"
	@echo "=============="
	@echo "Python: $(shell python --version)"
	@echo "Streamlit: $(shell pip show streamlit | grep Version)"
	@echo ""
	@echo "Comandos útiles:"
	@echo "  make dev          - Iniciar app"
	@echo "  make test         - Ejecutar tests"
	@echo "  make lint         - Verificar código"
	@echo "  make format       - Formatear código"

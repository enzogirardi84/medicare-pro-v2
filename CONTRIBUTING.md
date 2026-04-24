# Guía de Contribución - Medicare Pro

¡Gracias por tu interés en contribuir a Medicare Pro! Este documento te guiará en el proceso de contribución.

## 🚀 Cómo Contribuir

### 1. Configuración del Entorno

```bash
# Clonar el repositorio
git clone https://github.com/enzogirardi84/medicare-pro-v2.git
cd medicare-pro-v2

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Instalar dependencias
make install-dev

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores
```

### 2. Flujo de Trabajo

#### Crear una Rama

```bash
# Desde main o develop
git checkout -b feature/nombre-descriptivo

# Ejemplos:
# feature/nuevo-modulo-pediatria
# fix/validacion-dni
# docs/mejorar-api-docs
```

#### Desarrollo

```bash
# Iniciar app en modo desarrollo
make dev

# Ejecutar tests durante desarrollo
make test-unit

# Verificar código
make lint
make format-check
```

#### Commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: agregar soporte para múltiples clínicas
fix: corregir validación de email
docs: actualizar README con nuevas features
test: agregar tests para cache manager
refactor: optimizar queries de pacientes
```

#### Pre-commit Hooks

```bash
# Instalar hooks
make pre-commit

# O ejecutar manualmente
./scripts/pre-commit-check.sh
```

### 3. Tests

#### Estructura de Tests

```
tests/
├── test_<modulo>.py          # Tests unitarios
├── test_integration_<flujo>.py  # Tests de integración
├── test_e2e/                  # Tests E2E con Playwright
└── conftest.py               # Fixtures compartidos
```

#### Ejecutar Tests

```bash
# Todos los tests
make test

# Con cobertura
make test-coverage

# Solo unitarios
make test-unit

# Solo integración
make test-integration

# E2E
make test-e2e
```

#### Escribir Tests

```python
# test_ejemplo.py
def test_funcion_basica():
    """Test descriptivo de qué se está probando."""
    from core.utils import funcion_a_probar
    
    resultado = funcion_a_probar("input")
    
    assert resultado == "output_esperado"


def test_con_fixture(client):
    """Test usando fixtures."""
    response = client.get("/api/health")
    assert response.status_code == 200
```

### 4. Calidad de Código

#### Linting

- **Ruff**: Linter rápido y completo
- **MyPy**: Type checking
- **Bandit**: Seguridad

```bash
make lint
make security-check
```

#### Formato

- **Black**: Formateador de código
- **isort**: Ordenamiento de imports

```bash
make format        # Aplicar formato
make format-check  # Verificar sin modificar
```

#### Type Hints

Todos los módulos nuevos deben usar type hints:

```python
from typing import Dict, List, Optional

def procesar_pacientes(
    pacientes: List[Dict[str, Any]],
    limite: Optional[int] = None
) -> Dict[str, int]:
    """Procesa lista de pacientes y retorna estadísticas."""
    if limite:
        pacientes = pacientes[:limite]
    
    return {
        "total": len(pacientes),
        "activos": sum(1 for p in pacientes if p.get("activo"))
    }
```

### 5. Documentación

#### Docstrings

Usa formato Google/NumPy:

```python
def crear_paciente(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea un nuevo paciente en el sistema.

    Args:
        datos: Diccionario con datos del paciente.
            Requiere: nombre, apellido, dni
            Opcional: email, telefono, direccion

    Returns:
        Diccionario con paciente creado incluyendo ID.

    Raises:
        ValidationError: Si faltan campos requeridos.
        DuplicateError: Si el DNI ya existe.

    Example:
        >>> paciente = crear_paciente({
        ...     "nombre": "Juan",
        ...     "apellido": "Pérez",
        ...     "dni": "12345678"
        ... })
        >>> print(paciente["id"])
        'uuid-generado'
    """
```

#### README y Docs

- Actualizar README.md si agregas features
- Documentar API en `api/openapi.yaml`
- Agregar ejemplos en `docs/`

### 6. Pull Requests

#### Antes de Crear PR

```bash
# 1. Actualizar con main/develop
git fetch origin
git rebase origin/main

# 2. Ejecutar tests
make test

# 3. Verificar calidad
make lint
make format-check
make security-check

# 4. Verificar cobertura
make test-coverage
```

#### Estructura del PR

```markdown
## Descripción
Breve descripción de los cambios.

## Tipo de Cambio
- [ ] Bug fix
- [ ] Nueva feature
- [ ] Breaking change
- [ ] Documentación

## Checklist
- [ ] Tests agregados/actualizados
- [ ] Documentación actualizada
- [ ] Linting pasa
- [ ] Código formateado
- [ ] Pre-commit hooks pasan

## Screenshots (si aplica)
Adjuntar screenshots de UI changes.
```

### 7. Revisión de Código

#### Criterios de Revisión

- ✅ Código claro y mantenible
- ✅ Tests apropiados
- ✅ Documentación actualizada
- ✅ No hay código duplicado
- ✅ Manejo de errores apropiado
- ✅ Performance considerada
- ✅ Seguridad verificada

### 8. Release Process

1. Actualizar CHANGELOG.md
2. Actualizar version en `pyproject.toml`
3. Crear tag de versión
4. Merge a main
5. CI/CD ejecuta deploy

## 🛠️ Herramientas

### Makefile

```bash
make help           # Ver todos los comandos
make dev            # Iniciar desarrollo
make test           # Ejecutar tests
make lint           # Verificar código
make format         # Formatear código
make clean          # Limpiar temporales
```

### Docker

```bash
# Iniciar stack completo
make dev-docker

# Ver logs
make logs

# Detener
make stop-docker
```

## 📚 Recursos

- [Arquitectura](docs/ARCHITECTURE.md)
- [API Documentation](docs/api/README.md)
- [Roadmap](docs/ROADMAP_MEJORAS.md)
- [Plan de Mejoras](docs/PLAN_MEJORAS_PROFESIONAL.md)

## ❓ Preguntas Frecuentes

**¿Cómo reporto un bug?**
Crea un issue en GitHub con:
- Descripción del problema
- Pasos para reproducir
- Comportamiento esperado vs actual
- Screenshots/logs si aplica

**¿Puedo trabajar en issues existentes?**
¡Sí! Comenta en el issue para que te lo asignen.

**¿Hay alguna restricción de licencia?**
Este es un proyecto propietario. Contacta al autor para contribuciones mayores.

## 🤝 Código de Conducta

- Sé respetuoso y profesional
- Acepta feedback constructivo
- Enfócate en lo que es mejor para la comunidad
- Muestra empatía hacia otros colaboradores

---

**¡Gracias por contribuir a Medicare Pro! 🎉**

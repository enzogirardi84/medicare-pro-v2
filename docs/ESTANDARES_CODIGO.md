# Estándares de Código - MediCare Enterprise PRO

## Reglas de Oro para Desarrollo en Salud

### 1. Seguridad Total

#### Zero Hardcodeo de Credenciales
- **NUNCA** hardcodear secrets, tokens, ni contraseñas
- Usar `SecretStr` de Pydantic para todas las credenciales
- Las variables de entorno son la única fuente de truth en producción

```python
# ✅ CORRECTO
from pydantic import SecretStr

class Settings(BaseSettings):
    supabase_key: SecretStr

# ❌ INCORRECTO
SUPABASE_KEY = "eyJhbG..."
```

#### Validación de Entradas con Pydantic
- **TODOS** los inputs de usuario son potencialmente maliciosos
- Validar y sanitizar antes de tocar la base de datos
- Usar `core/security_middleware.py` para sanitización

```python
# ✅ CORRECTO
from core.security_middleware import InputSanitizer, PatientDataValidator

dni_limpio = PatientDataValidator.validate_dni(dni_input)
datos_sanitizados = InputSanitizer.sanitize_dict(datos_raw)

# ❌ INCORRECTO
paciente.dni = request.POST["dni"]  # Sin validación!
```

#### Soft Delete Obligatorio
- **NUNCA** hacer DELETE real de datos clínicos
- Siempre usar campo `estado = 'inactivo'`
- Mantener trazabilidad completa

### 2. Performance en Streamlit

#### Uso Intensivo de Caché

```python
# ✅ Datos estáticos (1 hora)
@st.cache_data(ttl=3600, show_spinner=False)
def get_obras_sociales():
    return [...]

# ✅ Datos de configuración (10 min)
@st.cache_data(ttl=600, show_spinner=False)
def get_app_config():
    return {...}

# ✅ Recursos no serializables (1x por proceso)
@st.cache_resource
def get_pdf_templates():
    return {...}
```

#### Paginación Obligatoria
- **NUNCA** cargar más de 100 registros sin paginar
- Usar `core/db_paginated.py` para todas las consultas
- Cursor-based pagination para grandes volúmenes

```python
# ✅ CORRECTO
from core.db_paginated import get_paginated_patients

result = get_paginated_patients(
    page=1,
    page_size=50,  # Máximo 100
    search=termino
)

# ❌ INCORRECTO
todos_los_pacientes = supabase.table("pacientes").select("*").execute()
```

#### Connection Pooling
- Usar puerto 6543 de Supabase para connection pool
- Pool size configurable via `CONNECTION_POOL_SIZE`

### 3. Calidad de Código

#### Type Hints Obligatorios
```python
# ✅ CORRECTO
def buscar_paciente(dni: str) -> Optional[Dict[str, Any]]:
    ...

# ❌ INCORRECTO
def buscar_paciente(dni):  # Sin tipos!
    ...
```

#### Modularidad Extrema
- Máximo 50 líneas por función
- Separar: UI (Streamlit) | Lógica (Business) | Datos (CRUD)
- Un archivo por responsabilidad

#### Manejo de Errores Explícito
```python
# ✅ CORRECTO
try:
    resultado = operacion_riesgosa()
except DatabaseError as e:
    log_event("db_error", f"operacion_fallo:{e}")
    st.error("Error al guardar. Intente nuevamente.")
    raise

# ❌ INCORRECTO
try:
    operacion_riesgosa()
except:
    pass  # Silenciar errores = CRÍTICO en salud!
```

### 4. Auditoría y Compliance

#### Decoradores de Auditoría
```python
from core.patient_audit_wrapper import requires_auth, audit_action

@requires_auth(roles=["medico", "admin"])
@audit_action(action="UPDATE", resource_type="patient")
def actualizar_paciente(patient_id: str, datos: dict):
    ...
```

#### Logs Inmutables
- Usar `core/audit_trail.py` para operaciones críticas
- Todos los logs deben incluir: timestamp, user_id, action, status

### 5. Librerías Modernas (Python 3.10+)

#### Siempre usar versiones recientes
```
pydantic>=2.0.0        # No v1.x
supabase>=2.0.0        # Cliente moderno
cryptography>=42.0.0   # Seguridad actualizada
bleach>=6.0.0          # Sanitización HTML
```

#### NUNCA usar librerías obsoletas
```python
# ❌ PROHIBIDO
from datetime import datetime
ahora = datetime.utcnow()  # Deprecado!

# ✅ CORRECTO
from datetime import datetime, timezone
ahora = datetime.now(timezone.utc)
```

## Estructura de Archivos

```
core/
├── config_secure.py           # Configuración con SecretStr
├── security_middleware.py     # Sanitización y validación
├── db_paginated.py           # Consultas paginadas
├── cache_optimized.py        # Sistema de caché
├── patient_audit_wrapper.py # Servicio de pacientes con auditoría
└── ...
```

## Checklist antes de commit

- [ ] Sin secrets hardcodeados
- [ ] Type hints completos
- [ ] Validación de inputs con Pydantic
- [ ] Paginación en consultas grandes
- [ ] Decoradores de auditoría en operaciones críticas
- [ ] Tests pasando
- [ ] Mensaje de commit descriptivo en español

---

**Última actualización:** 2026-04-24
**Versión estándar:** 1.0.0

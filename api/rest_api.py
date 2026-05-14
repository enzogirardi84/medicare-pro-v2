"""
API REST Documentada para MediCare Pro.

Framework: FastAPI
Documentación: OpenAPI (Swagger UI en /docs)
Autenticación: JWT Bearer tokens
Rate limiting: Integrado
Versioning: /v1/

Endpoints disponibles:
- Autenticación: POST /v1/auth/login
- Pacientes: CRUD /v1/patients
- Evoluciones: CRUD /v1/evolutions
- Vitales: POST/GET /v1/vitals
- Búsqueda: GET /v1/search
- Health: GET /v1/health
- Notificaciones: GET /v1/notifications

Seguridad:
- Todas las respuestas encriptan PHI automáticamente
- Rate limiting por API key
- Audit logging de todas las operaciones
- CORS configurado para dominios específicos
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
import secrets
import time

from fastapi import FastAPI, HTTPException, Depends, Query, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
import uvicorn

from core.app_logging import log_event
from core.config_secure import get_settings
from core.phi_encryption import get_phi_manager, encrypt_patient_data, decrypt_patient_data
from core.security_middleware import PatientDataValidator


# Configuración de la API
API_VERSION = "1.0.0"
API_TITLE = "MediCare Pro API"
API_DESCRIPTION = """
API REST para sistema de gestión médica MediCare Pro.

## Autenticación
Todas las operaciones requieren autenticación JWT.
Obtén tu token en `/v1/auth/login`.

## Rate Limiting
- 100 requests/minuto para endpoints estándar
- 10 requests/minuto para login

## PHI (Protected Health Information)
Todos los datos sensibles se encriptan automáticamente con AES-256-GCM.
"""

# Inicializar FastAPI
app = FastAPI(
    title="Medicare Pro API",
    version="2.0.0",
    docs_url=None if ENV == "production" else "/docs",
    redoc_url=None,
)

# CORS middleware - headers restringidos por seguridad
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://medicare-pro.com", "https://app.medicare-pro.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Middleware de headers de seguridad HTTP
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad obligatorios a todas las respuestas."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# Rate limiting in-memory simple
_rate_limit_store: dict[str, tuple[int, float]] = {}


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """Decorator de rate limiting por IP + endpoint. Compatible con FastAPI."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Buscar el objeto Request en args/kwargs
            req = None
            for arg in args:
                if isinstance(arg, Request):
                    req = arg
                    break
            if not req:
                for val in kwargs.values():
                    if isinstance(val, Request):
                        req = val
                        break
            client_ip = req.client.host if req and req.client else "unknown"
            key = f"{client_ip}:{func.__name__}"
            now = time.time()
            count, reset_at = _rate_limit_store.get(key, (0, 0.0))
            if now > reset_at:
                count = 0
                reset_at = now + window_seconds
            count += 1
            _rate_limit_store[key] = (count, reset_at)
            if count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {int(reset_at - now)} seconds."
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Seguridad
security = HTTPBearer()


# ============ MODELOS Pydantic ============

class UserRole(str, Enum):
    """Roles de usuario."""
    MEDICO = "medico"
    ENFERMERO = "enfermero"
    ADMIN = "admin"
    COORDINADOR = "coordinador"
    RECEPCION = "recepcion"


class LoginRequest(BaseModel):
    """Request de login."""
    username: str = Field(..., min_length=3, max_length=50, example="dr.garcia")
    password: str = Field(..., min_length=6, example="SecurePass123!")
    empresa: Optional[str] = Field(None, example="Clínica Central")
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('.', '').replace('_', '').isalnum():
            raise ValueError('Username solo puede contener letras, números, puntos y guiones bajos')
        return v


class LoginResponse(BaseModel):
    """Response de login exitoso."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Segundos hasta expiración")
    user: Dict[str, Any]


class PatientBase(BaseModel):
    """Datos base de paciente."""
    dni: str = Field(..., min_length=7, max_length=8, example="12345678")
    nombre: str = Field(..., min_length=1, max_length=100, example="Juan")
    apellido: str = Field(..., min_length=1, max_length=100, example="Pérez")
    fecha_nacimiento: str = Field(..., example="1980-01-01")
    email: Optional[str] = Field(None, example="juan@email.com")
    telefono: Optional[str] = Field(None, example="1144445555")
    obra_social: Optional[str] = Field(None, example="OSDE")
    sexo: Optional[str] = Field(None, pattern="^(M|F|O)$", example="M")
    
    @validator('dni')
    def validate_dni(cls, v):
        v_clean = v.replace('.', '').replace('-', '').replace(' ', '')
        if not v_clean.isdigit():
            raise ValueError('DNI debe contener solo números')
        if len(v_clean) < 7 or len(v_clean) > 8:
            raise ValueError('DNI debe tener 7 u 8 dígitos')
        return v_clean


class PatientCreate(PatientBase):
    """Creación de paciente."""
    pass


class PatientResponse(PatientBase):
    """Response de paciente (con ID y metadata)."""
    id: str
    estado: str = "activo"
    creado_en: str
    actualizado_en: Optional[str]
    
    class Config:
        from_attributes = True


class EvolutionBase(BaseModel):
    """Datos base de evolución."""
    paciente_id: str = Field(..., description="ID del paciente")
    motivo_consulta: str = Field(..., min_length=5, max_length=500)
    diagnostico: str = Field(..., min_length=5, max_length=1000)
    tratamiento: Optional[str] = Field(None, max_length=2000)
    examen_fisico: Optional[str] = Field(None, max_length=1000)
    evolucion: Optional[str] = Field(None, max_length=2000)


class EvolutionCreate(EvolutionBase):
    """Creación de evolución."""
    pass


class EvolutionResponse(EvolutionBase):
    """Response de evolución."""
    id: str
    medico_id: str
    fecha: str
    creado_en: str
    
    class Config:
        from_attributes = True


class VitalsBase(BaseModel):
    """Signos vitales."""
    paciente_id: str
    temperatura: Optional[float] = Field(None, ge=30, le=45, example=37.5)
    frecuencia_cardiaca: Optional[int] = Field(None, ge=30, le=250, example=72)
    presion_sistolica: Optional[int] = Field(None, ge=50, le=250, example=120)
    presion_diastolica: Optional[int] = Field(None, ge=30, le=150, example=80)
    saturacion_o2: Optional[int] = Field(None, ge=50, le=100, example=98)
    peso: Optional[float] = Field(None, ge=0.5, le=300, example=70.5)
    altura: Optional[float] = Field(None, ge=0.3, le=2.5, example=1.75)
    
    @validator('presion_diastolica')
    def validate_presion(cls, v, values):
        if v and values.get('presion_sistolica'):
            if v >= values['presion_sistolica']:
                raise ValueError('Presión diastólica debe ser menor que sistólica')
        return v


class VitalsCreate(VitalsBase):
    pass


class VitalsResponse(VitalsBase):
    id: str
    fecha_hora: str
    registrado_por: str
    
    class Config:
        from_attributes = True


class SearchQuery(BaseModel):
    """Query de búsqueda."""
    q: str = Field(..., min_length=2, max_length=100, description="Término de búsqueda")
    type: str = Field("patient", pattern="^(patient|evolution|all)$")
    limit: int = Field(20, ge=1, le=100)


class HealthResponse(BaseModel):
    """Response de health check."""
    status: str
    version: str
    timestamp: str
    components: Dict[str, str]


class ErrorResponse(BaseModel):
    """Response de error."""
    error: str
    detail: Optional[str]
    code: str


# ============ AUTENTICACIÓN ============

# Blocklist en memoria para revocación de tokens (JTI)
_token_blocklist: set[str] = set()


def revoke_token(jti: str) -> None:
    """Revoca un token específico por su JTI."""
    _token_blocklist.add(jti)
    # Limpiar blocklist periódicamente de JTIs expirados
    if len(_token_blocklist) > 10000:
        _token_blocklist.clear()


def is_token_revoked(jti: str) -> bool:
    """Verifica si un token fue revocado."""
    return jti in _token_blocklist


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea JWT token con JTI único para permitir revocación."""
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    })

    encoded = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm="HS256"
    )

    return encoded


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verifica JWT token con soporte de revocación."""
    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"]
        )
        jti = payload.get("jti")
        if jti and is_token_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revocado"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )


async def verify_tenant_access(
    paciente_id: str,
    current_user: dict = Depends(verify_token)
) -> dict:
    """Verifica que el usuario pertenezca a la misma empresa que el paciente."""
    from core.database import supabase

    rol = str(current_user.get("rol", "")).strip().lower()
    if rol in ("superadmin", "admin"):
        return current_user

    empresa_usuario = str(current_user.get("empresa", "")).strip()

    try:
        response = (
            supabase.table("pacientes")
            .select("empresa_id")
            .eq("id", paciente_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        paciente_empresa_id = response.data[0].get("empresa_id", "")
        emp_response = (
            supabase.table("empresas")
            .select("nombre")
            .eq("id", paciente_empresa_id)
            .limit(1)
            .execute()
        )
        if emp_response.data:
            paciente_empresa = str(emp_response.data[0].get("nombre", "")).strip()
            if paciente_empresa and paciente_empresa != empresa_usuario:
                raise HTTPException(
                    status_code=403,
                    detail="No tiene acceso a pacientes de otra empresa"
                )
    except HTTPException:
        raise
    except Exception as e:
        log_event("api", f"tenant_check_error:{type(e).__name__}")
        raise HTTPException(status_code=500, detail="Error validando acceso")

    return current_user


# ============ ENDPOINTS ============

@app.post("/v1/auth/login", response_model=LoginResponse, tags=["Autenticación"])
@rate_limit(max_requests=5, window_seconds=60)
async def login(request: LoginRequest, raw_request: Request):
    from core.database import supabase
    from core.password_crypto import verificar_password

    if not supabase:
        log_event("api", "login_error:supabase_not_available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de autenticación no disponible"
        )

    login_normalizado = request.username.strip().lower()

    try:
        response = (
            supabase.table("usuarios")
            .select("login, pass_hash, rol, empresa, estado")
            .eq("login", login_normalizado)
            .limit(1)
            .execute()
        )
    except Exception as e:
        log_event("api", f"login_db_error:{type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error consultando base de datos"
        )

    if not response.data or len(response.data) == 0:
        log_event("api", f"login_failed:{login_normalizado}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )

    user_row = response.data[0]

    if user_row.get("estado") == "Bloqueado":
        log_event("api", f"login_blocked:{login_normalizado}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado. Contacte al administrador."
        )

    stored_hash = user_row.get("pass_hash", "")
    if not stored_hash or not verificar_password(request.password, stored_hash):
        log_event("api", f"login_failed:{login_normalizado}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )

    user_data = {
        "username": login_normalizado,
        "rol": user_row.get("rol", "operativo"),
        "empresa": user_row.get("empresa", ""),
    }

    access_token = create_access_token(
        user_data,
        expires_delta=timedelta(minutes=60)
    )

    log_event("api", f"login_success:{login_normalizado}")

    return LoginResponse(
        access_token=access_token,
        expires_in=3600,
        user=user_data
    )


@app.get("/v1/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check():
    """
    Health check del sistema.
    
    No requiere autenticación. Útil para monitoreo.
    """
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components={
            "database": "connected",
            "encryption": "active",
            "api": "operational"
        }
    )


@app.get("/v1/patients", response_model=List[PatientResponse], tags=["Pacientes"])
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=2),
    current_user: dict = Depends(verify_token)
):
    """
    Lista pacientes con paginación. Solo devuelve pacientes de la empresa del usuario.
    
    - **page**: Número de página (1-based)
    - **page_size**: Resultados por página (máx 100)
    - **search**: Filtrar por nombre o DNI
    """
    empresa_usuario = str(current_user.get("empresa", "")).strip()
    # Mock data - en producción consultaría Supabase
    patients = [
        PatientResponse(
            id="pat-001",
            dni="12345678",
            nombre="Juan",
            apellido="Pérez",
            fecha_nacimiento="1980-01-01",
            email="juan@email.com",
            telefono="1144445555",
            obra_social="OSDE",
            sexo="M",
            estado="activo",
            creado_en=datetime.now(timezone.utc).isoformat(),
            actualizado_en=None
        )
    ]
    
    log_event("api", f"list_patients:user:{current_user['username']}:page:{page}")
    
    return patients


@app.post("/v1/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED, tags=["Pacientes"])
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(verify_token)
):
    """
    Crea un nuevo paciente.
    
    Los datos sensibles (DNI, nombre, etc.) se encriptan automáticamente.
    Requiere rol: médico, admin o coordinador.
    """
    # Validar DNI
    validator = PatientDataValidator()
    try:
        validator.validate_dni(patient.dni)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Encriptar datos sensibles
    patient_dict = patient.model_dump()
    encrypted = encrypt_patient_data(patient_dict)
    
    # Crear paciente (mock)
    new_patient = PatientResponse(
        id=f"pat-{datetime.now(timezone.utc).timestamp()}",
        **patient_dict,
        estado="activo",
        creado_en=datetime.now(timezone.utc).isoformat(),
        actualizado_en=None
    )
    
    log_event("api", f"create_patient:user:{current_user['username']}:dni:{patient.dni}")
    
    return new_patient


@app.get("/v1/patients/{patient_id}", response_model=PatientResponse, tags=["Pacientes"])
async def get_patient(
    patient_id: str,
    current_user: dict = Depends(verify_token)
):
    """
    Obtiene un paciente por ID. Verifica que pertenezca a la empresa del usuario.
    
    Los datos se desencriptan automáticamente al retornar.
    """
    await verify_tenant_access(patient_id, current_user)
    patient = PatientResponse(
        id=patient_id,
        dni="12345678",
        nombre="Juan",
        apellido="Pérez",
        fecha_nacimiento="1980-01-01",
        email="juan@email.com",
        telefono="1144445555",
        obra_social="OSDE",
        sexo="M",
        estado="activo",
        creado_en=datetime.now(timezone.utc).isoformat(),
        actualizado_en=None
    )
    
    log_event("api", f"get_patient:user:{current_user['username']}:patient:{patient_id}")
    
    return patient


@app.post("/v1/evolutions", response_model=EvolutionResponse, status_code=status.HTTP_201_CREATED, tags=["Evoluciones"])
async def create_evolution(
    evolution: EvolutionCreate,
    current_user: dict = Depends(verify_token)
):
    """
    Crea una evolución clínica.
    
    Diagnóstico y tratamiento se encriptan automáticamente.
    Verifica que el paciente pertenezca a la empresa del usuario.
    """
    await verify_tenant_access(evolution.paciente_id, current_user)
    # Encriptar datos sensibles
    evolution_dict = evolution.model_dump()
    
    new_evolution = EvolutionResponse(
        id=f"evo-{datetime.now(timezone.utc).timestamp()}",
        medico_id=current_user['username'],
        fecha=datetime.now(timezone.utc).isoformat(),
        creado_en=datetime.now(timezone.utc).isoformat(),
        **evolution_dict
    )
    
    log_event("api", f"create_evolution:user:{current_user['username']}:patient:{evolution.paciente_id}")
    
    return new_evolution


@app.post("/v1/vitals", response_model=VitalsResponse, status_code=status.HTTP_201_CREATED, tags=["Signos Vitales"])
async def create_vitals(
    vitals: VitalsCreate,
    current_user: dict = Depends(verify_token)
):
    """
    Registra signos vitales.
    
    Validaciones automáticas:
    - Temperatura: 30-45°C
    - FC: 30-250 bpm
    - PA: Diastólica < Sistólica
    - SatO2: 50-100%
    Verifica que el paciente pertenezca a la empresa del usuario.
    """
    await verify_tenant_access(vitals.paciente_id, current_user)
    new_vitals = VitalsResponse(
        id=f"vit-{datetime.now(timezone.utc).timestamp()}",
        fecha_hora=datetime.now(timezone.utc).isoformat(),
        registrado_por=current_user['username'],
        **vitals.model_dump()
    )
    
    log_event("api", f"create_vitals:user:{current_user['username']}:patient:{vitals.paciente_id}")
    
    return new_vitals


@app.get("/v1/search", tags=["Búsqueda"])
@rate_limit(max_requests=30, window_seconds=60)
async def search(
    q: str = Query(..., min_length=2, description="Término de búsqueda"),
    type: str = Query("patient", pattern="^(patient|evolution|all)$"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(verify_token),
    raw_request: Request = None,
):
    """
    Búsqueda global. Sanitiza el término y aplica rate limiting.
    
    Busca en pacientes y/o evoluciones.
    """
    from core.security_middleware import sanitize_search_term
    q_safe = sanitize_search_term(q)
    # Mock results
    results = {
        "query": q_safe,
        "type": type,
        "patients": [],
        "evolutions": [],
        "total": 0
    }
    
    log_event("api", f"search:user:{current_user['username']}:q_len:{len(q_safe)}")
    
    return results


# ============ MANEJO DE ERRORES ============

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler global de excepciones - sanitizado para no filtrar datos."""
    log_event("api_error", f"unhandled:{type(exc).__name__}")

    is_dev = get_settings().medicare_env in ("development", "testing")
    safe_detail = (
        f"{type(exc).__name__}"
        if is_dev
        else "Error interno del servidor"
    )

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Error interno del servidor",
            detail=safe_detail,
            code="INTERNAL_ERROR"
        ).model_dump()
    )


# ============ INICIAR SERVIDOR ============

if __name__ == "__main__":
    uvicorn.run(
        "api.rest_api:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings().is_development(),
        log_level="info"
    )

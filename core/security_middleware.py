"""
Middleware de Seguridad para MediCare Pro.

Sanitización de inputs, prevención XSS/SQL injection, y validación de datos.
"""
import re
import html
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from bleach import clean
import bleach.sanitizer


# Patrones de detección de ataques
SQL_INJECTION_PATTERNS = [
    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
    r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
    r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
    r"((\%27)|(\'))union",
    r"exec(\s|\+)+(s|x)p\w+",
    r"UNION\s+SELECT",
    r"INSERT\s+INTO",
    r"DELETE\s+FROM",
    r"DROP\s+TABLE",
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
]

DANGEROUS_EXTENSIONS = [
    ".exe", ".dll", ".bat", ".cmd", ".sh", ".php", ".jsp", ".asp",
    ".aspx", ".py", ".rb", ".pl", ".cgi"
]


class SecurityError(Exception):
    """Error de seguridad detectado."""
    pass


class InputSanitizer:
    """Sanitizador de inputs con prevención XSS y SQL injection."""
    
    # Tags HTML permitidos para campos de texto rico (evoluciones, notas)
    ALLOWED_TAGS = [
        "p", "br", "strong", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "a", "blockquote", "code", "pre"
    ]
    
    ALLOWED_ATTRIBUTES = {
        "a": ["href", "title"],
        "*": ["class"]
    }
    
    @classmethod
    def detect_sql_injection(cls, value: str) -> bool:
        """Detecta patrones de SQL injection."""
        value_upper = str(value).upper()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def detect_xss(cls, value: str) -> bool:
        """Detecta patrones de XSS."""
        for pattern in XSS_PATTERNS:
            if re.search(pattern, str(value), re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def sanitize_string(cls, value: str, allow_html: bool = False) -> str:
        """
        Sanitiza string de input.
        
        Args:
            value: Valor a sanitizar
            allow_html: Si True, permite tags HTML seguros. Si False, escapa todo HTML.
        """
        if value is None:
            return ""
        
        value = str(value).strip()
        
        # Detectar ataques
        if cls.detect_sql_injection(value):
            raise SecurityError(f"Posible ataque SQL injection detectado: {value[:50]}...")
        
        if not allow_html and cls.detect_xss(value):
            raise SecurityError(f"Posible ataque XSS detectado: {value[:50]}...")
        
        if allow_html:
            # Permitir HTML seguro con bleach
            return clean(
                value,
                tags=cls.ALLOWED_TAGS,
                attributes=cls.ALLOWED_ATTRIBUTES,
                strip=True
            )
        else:
            # Escapar HTML completamente
            return html.escape(value)
    
    @classmethod
    def sanitize_dict(
        cls,
        data: Dict[str, Any],
        allow_html_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Sanitiza todos los valores de un diccionario."""
        allow_html_fields = allow_html_fields or []
        result = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                allow_html = key in allow_html_fields
                result[key] = cls.sanitize_string(value, allow_html=allow_html)
            elif isinstance(value, dict):
                result[key] = cls.sanitize_dict(value, allow_html_fields)
            elif isinstance(value, list):
                result[key] = cls.sanitize_list(value, allow_html_fields)
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def sanitize_list(
        cls,
        data: List[Any],
        allow_html_fields: Optional[List[str]] = None
    ) -> List[Any]:
        """Sanitiza todos los elementos de una lista."""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(cls.sanitize_string(item))
            elif isinstance(item, dict):
                result.append(cls.sanitize_dict(item, allow_html_fields))
            elif isinstance(item, list):
                result.append(cls.sanitize_list(item, allow_html_fields))
            else:
                result.append(item)
        return result


class PatientDataValidator:
    """Validador específico para datos de pacientes."""
    
    # Rangos médicos válidos
    PESO_MIN = 0.5  # kg
    PESO_MAX = 300.0
    ALTURA_MIN = 0.3  # metros
    ALTURA_MAX = 2.5
    TEMP_MIN = 30.0
    TEMP_MAX = 45.0
    FC_MIN = 30  # Frecuencia cardíaca
    FC_MAX = 250
    SAT_O2_MIN = 50
    SAT_O2_MAX = 100
    
    @classmethod
    def validate_dni(cls, dni: str) -> str:
        """Valida y normaliza DNI argentino."""
        if not dni:
            raise ValueError("DNI es requerido")
        
        # Limpiar
        dni_clean = str(dni).strip().replace(".", "").replace("-", "").replace(" ", "")
        
        # Verificar numérico
        if not dni_clean.isdigit():
            raise ValueError("DNI debe contener solo números")
        
        # Verificar longitud
        if len(dni_clean) < 7 or len(dni_clean) > 8:
            raise ValueError(f"DNI debe tener 7 u 8 dígitos (tiene {len(dni_clean)})")
        
        return dni_clean
    
    @classmethod
    def validate_email(cls, email: Optional[str]) -> Optional[str]:
        """Valida email."""
        if not email:
            return None
        
        email = str(email).strip().lower()
        
        # Longitud máxima
        if len(email) > 254:
            raise ValueError("Email demasiado largo")
        
        # Patrón simple pero efectivo
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError(f"Formato de email inválido: {email}")
        
        return email
    
    @classmethod
    def validate_telefono(cls, telefono: Optional[str]) -> Optional[str]:
        """Valida número de teléfono."""
        if not telefono:
            return None
        
        # Limpiar
        tel = str(telefono).strip()
        for char in [' ', '-', '(', ')', '.', '+']:
            tel = tel.replace(char, '')
        
        # Verificar longitud
        if len(tel) < 8:
            raise ValueError("Número de teléfono demasiado corto")
        if len(tel) > 15:
            raise ValueError("Número de teléfono demasiado largo")
        
        # Verificar numérico (excepto posible + inicial)
        digits_only = tel.lstrip('+')
        if not digits_only.isdigit():
            raise ValueError("Teléfono debe contener solo números")
        
        return tel
    
    @classmethod
    def validate_signos_vitales(
        cls,
        temperatura: Optional[float] = None,
        frecuencia_cardiaca: Optional[int] = None,
        presion_sistolica: Optional[int] = None,
        presion_diastolica: Optional[int] = None,
        saturacion_o2: Optional[int] = None,
        peso: Optional[float] = None,
        altura: Optional[float] = None
    ) -> Dict[str, Any]:
        """Valida signos vitales y retorna solo los válidos."""
        result = {}
        errors = []
        
        if temperatura is not None:
            if cls.TEMP_MIN <= temperatura <= cls.TEMP_MAX:
                result["temperatura"] = round(temperatura, 1)
            else:
                errors.append(f"Temperatura fuera de rango ({cls.TEMP_MIN}-{cls.TEMP_MAX}°C)")
        
        if frecuencia_cardiaca is not None:
            if cls.FC_MIN <= frecuencia_cardiaca <= cls.FC_MAX:
                result["frecuencia_cardiaca"] = frecuencia_cardiaca
            else:
                errors.append(f"Frecuencia cardíaca fuera de rango ({cls.FC_MIN}-{cls.FC_MAX})")
        
        if presion_sistolica is not None and presion_diastolica is not None:
            if presion_sistolica > presion_diastolica:
                result["presion_sistolica"] = presion_sistolica
                result["presion_diastolica"] = presion_diastolica
            else:
                errors.append("Presión sistólica debe ser mayor que diastólica")
        
        if saturacion_o2 is not None:
            if cls.SAT_O2_MIN <= saturacion_o2 <= cls.SAT_O2_MAX:
                result["saturacion_o2"] = saturacion_o2
            else:
                errors.append(f"Saturación O2 fuera de rango ({cls.SAT_O2_MIN}-{cls.SAT_O2_MAX}%)")
        
        if peso is not None:
            if cls.PESO_MIN <= peso <= cls.PESO_MAX:
                result["peso"] = round(peso, 2)
            else:
                errors.append(f"Peso fuera de rango ({cls.PESO_MIN}-{cls.PESO_MAX} kg)")
        
        if altura is not None:
            if cls.ALTURA_MIN <= altura <= cls.ALTURA_MAX:
                result["altura"] = round(altura, 2)
            else:
                errors.append(f"Altura fuera de rango ({cls.ALTURA_MIN}-{cls.ALTURA_MAX} m)")
        
        return {"validos": result, "errores": errors}


def sanitize_clinical_text(text: str) -> str:
    """
    Sanitiza texto clínico permitiendo formato HTML básico.
    Usar para evoluciones, notas de enfermería, etc.
    """
    return InputSanitizer.sanitize_string(text, allow_html=True)


def sanitize_search_term(term: str) -> str:
    """
    Sanitiza término de búsqueda - máxima seguridad, sin HTML.
    """
    return InputSanitizer.sanitize_string(term, allow_html=False)

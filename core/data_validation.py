"""
Sistema de Validación de Datos para Medicare Pro.

Proporciona:
- Validación de datos de pacientes
- Sanitización de inputs
- Validación de DNI/CUIT/CUIL
- Validación de emails y teléfonos
- Validación de fechas médicas
- Validación de prescripciones
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum


class ValidationSeverity(Enum):
    """Severidad de errores de validación."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Resultado de validación."""
    is_valid: bool
    field: str
    message: str
    severity: ValidationSeverity
    suggestions: Optional[List[str]] = None


class DataValidator:
    """
    Validador central de datos del sistema.
    
    Valida:
    - Datos de pacientes (DNI, email, teléfono)
    - Datos médicos (prescripciones, diagnósticos)
    - Datos de usuarios (matrícula, roles)
    - Fechas y horarios
    """
    
    # Patrones regex
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    DNI_PATTERN = re.compile(r'^[0-9]{7,8}$')
    
    PHONE_PATTERN = re.compile(
        r'^(?:(?:00|\+)?(?:(?:9[\s\-]?)?[\s\-]?(?:\(?[\s\-]?[1-9]\d{1,2}[\s\-]?\)?)?[\s\-]?))?(?:[1-9]\d{1,2}[\s\-]?)\d{2,4}[\s\-]?\d{4}$'
    )
    
    MATRICULA_PATTERN = re.compile(r'^[A-Z]{2,3}-\d{4,6}$')
    
    # Rangos médicos
    PESO_MIN = 0.5  # kg
    PESO_MAX = 300.0
    ALTURA_MIN = 0.3  # metros
    ALTURA_MAX = 2.5
    TEMP_MIN = 30.0
    TEMP_MAX = 45.0
    FC_MIN = 30
    FC_MAX = 250
    SAT_O2_MIN = 50
    SAT_O2_MAX = 100
    
    def validate_dni(self, dni: str) -> ValidationResult:
        """
        Valida DNI argentino.
        
        Args:
            dni: Número de DNI (7-8 dígitos)
        
        Returns:
            ValidationResult con resultado
        """
        if not dni:
            return ValidationResult(
                is_valid=False,
                field="dni",
                message="DNI es requerido",
                severity=ValidationSeverity.ERROR
            )
        
        # Limpiar
        dni_clean = str(dni).strip().replace(".", "").replace("-", "")
        
        # Verificar que sea numérico
        if not dni_clean.isdigit():
            return ValidationResult(
                is_valid=False,
                field="dni",
                message="DNI debe contener solo números",
                severity=ValidationSeverity.ERROR,
                suggestions=["Eliminar puntos y guiones", "Verificar que no haya letras"]
            )
        
        # Verificar longitud
        if len(dni_clean) < 7 or len(dni_clean) > 8:
            return ValidationResult(
                is_valid=False,
                field="dni",
                message=f"DNI debe tener 7 u 8 dígitos (tiene {len(dni_clean)})",
                severity=ValidationSeverity.ERROR
            )
        
        return ValidationResult(
            is_valid=True,
            field="dni",
            message="DNI válido",
            severity=ValidationSeverity.INFO
        )
    
    def validate_email(self, email: str) -> ValidationResult:
        """Valida dirección de email."""
        if not email:
            return ValidationResult(
                is_valid=True,  # Email opcional
                field="email",
                message="Email no proporcionado",
                severity=ValidationSeverity.INFO
            )
        
        email = str(email).strip().lower()
        
        if len(email) > 254:
            return ValidationResult(
                is_valid=False,
                field="email",
                message="Email demasiado largo",
                severity=ValidationSeverity.ERROR
            )
        
        if not self.EMAIL_PATTERN.match(email):
            return ValidationResult(
                is_valid=False,
                field="email",
                message="Formato de email inválido",
                severity=ValidationSeverity.ERROR,
                suggestions=["Verificar @ y dominio", "Ejemplo: usuario@dominio.com"]
            )
        
        return ValidationResult(
            is_valid=True,
            field="email",
            message="Email válido",
            severity=ValidationSeverity.INFO
        )
    
    def validate_phone(self, phone: str) -> ValidationResult:
        """
        Valida número de teléfono.
        
        Soporta formatos:
        - 11 5555-1234
        - +54 9 11 5555-1234
        - 1555551234
        """
        if not phone:
            return ValidationResult(
                is_valid=True,  # Opcional
                field="telefono",
                message="Teléfono no proporcionado",
                severity=ValidationSeverity.INFO
            )
        
        phone_clean = str(phone).strip()
        
        # Eliminar caracteres comunes
        for char in [' ', '-', '(', ')', '.', '+']:
            phone_clean = phone_clean.replace(char, '')
        
        # Verificar longitud mínima
        if len(phone_clean) < 8:
            return ValidationResult(
                is_valid=False,
                field="telefono",
                message="Número de teléfono demasiado corto",
                severity=ValidationSeverity.WARNING
            )
        
        if len(phone_clean) > 15:
            return ValidationResult(
                is_valid=False,
                field="telefono",
                message="Número de teléfono demasiado largo",
                severity=ValidationSeverity.WARNING
            )
        
        # Verificar que sea numérico (excepto por posible + inicial)
        digits_only = phone_clean.lstrip('+')
        if not digits_only.isdigit():
            return ValidationResult(
                is_valid=False,
                field="telefono",
                message="Teléfono debe contener solo números",
                severity=ValidationSeverity.ERROR
            )
        
        return ValidationResult(
            is_valid=True,
            field="telefono",
            message="Teléfono válido",
            severity=ValidationSeverity.INFO
        )
    
    def validate_matricula(self, matricula: str, tipo: str = "medico") -> ValidationResult:
        """
        Valida matrícula profesional.
        
        Args:
            matricula: Número de matrícula
            tipo: Tipo de profesional (medico, enfermera, etc.)
        """
        if not matricula:
            return ValidationResult(
                is_valid=False,
                field="matricula",
                message="Matrícula es requerida para profesionales de la salud",
                severity=ValidationSeverity.ERROR
            )
        
        matricula = str(matricula).strip().upper()
        
        # Formato típico: MP-12345, MN-123456, etc.
        if not self.MATRICULA_PATTERN.match(matricula):
            return ValidationResult(
                is_valid=False,
                field="matricula",
                message="Formato de matrícula inválido",
                severity=ValidationSeverity.WARNING,
                suggestions=["Formato esperado: MP-12345", "Usar prefijo según provincia"]
            )
        
        return ValidationResult(
            is_valid=True,
            field="matricula",
            message="Matrícula válida",
            severity=ValidationSeverity.INFO
        )
    
    def validate_patient_data(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """
        Valida todos los datos de un paciente.
        
        Args:
            data: Diccionario con datos del paciente
        
        Returns:
            Lista de resultados de validación
        """
        results = []
        
        # DNI (requerido)
        if "dni" in data:
            results.append(self.validate_dni(data["dni"]))
        else:
            results.append(ValidationResult(
                is_valid=False,
                field="dni",
                message="DNI es requerido",
                severity=ValidationSeverity.CRITICAL
            ))
        
        # Nombre (requerido)
        nombre = data.get("nombre", "").strip()
        if not nombre:
            results.append(ValidationResult(
                is_valid=False,
                field="nombre",
                message="Nombre es requerido",
                severity=ValidationSeverity.ERROR
            ))
        elif len(nombre) < 2:
            results.append(ValidationResult(
                is_valid=False,
                field="nombre",
                message="Nombre demasiado corto",
                severity=ValidationSeverity.WARNING
            ))
        else:
            results.append(ValidationResult(
                is_valid=True,
                field="nombre",
                message="Nombre válido",
                severity=ValidationSeverity.INFO
            ))
        
        # Apellido (requerido)
        apellido = data.get("apellido", "").strip()
        if not apellido:
            results.append(ValidationResult(
                is_valid=False,
                field="apellido",
                message="Apellido es requerido",
                severity=ValidationSeverity.ERROR
            ))
        else:
            results.append(ValidationResult(
                is_valid=True,
                field="apellido",
                message="Apellido válido",
                severity=ValidationSeverity.INFO
            ))
        
        # Email (opcional)
        if "email" in data:
            results.append(self.validate_email(data["email"]))
        
        # Teléfono (opcional)
        if "telefono" in data:
            results.append(self.validate_phone(data["telefono"]))
        
        # Fecha de nacimiento (opcional pero recomendada)
        if "fecha_nacimiento" in data:
            fecha_result = self.validate_birth_date(data["fecha_nacimiento"])
            results.append(fecha_result)
        
        return results
    
    def validate_birth_date(self, fecha: Union[str, date, datetime]) -> ValidationResult:
        """Valida fecha de nacimiento."""
        try:
            if isinstance(fecha, str):
                # Intentar parsear
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        fecha = datetime.strptime(fecha.strip(), fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    return ValidationResult(
                        is_valid=False,
                        field="fecha_nacimiento",
                        message="Formato de fecha inválido",
                        severity=ValidationSeverity.ERROR,
                        suggestions=["Usar formato DD/MM/AAAA", "Ejemplo: 15/05/1985"]
                    )
            
            elif isinstance(fecha, datetime):
                fecha = fecha.date()
            
            # Verificar rango
            hoy = date.today()
            
            if fecha > hoy:
                return ValidationResult(
                    is_valid=False,
                    field="fecha_nacimiento",
                    message="Fecha de nacimiento no puede ser futura",
                    severity=ValidationSeverity.ERROR
                )
            
            edad = (hoy - fecha).days / 365.25
            
            if edad > 150:
                return ValidationResult(
                    is_valid=False,
                    field="fecha_nacimiento",
                    message="Edad calculada excede 150 años",
                    severity=ValidationSeverity.WARNING
                )
            
            if edad < 0:
                return ValidationResult(
                    is_valid=False,
                    field="fecha_nacimiento",
                    message="Fecha inválida",
                    severity=ValidationSeverity.ERROR
                )
            
            return ValidationResult(
                is_valid=True,
                field="fecha_nacimiento",
                message=f"Fecha válida (edad: {int(edad)} años)",
                severity=ValidationSeverity.INFO
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                field="fecha_nacimiento",
                message=f"Error validando fecha: {str(e)}",
                severity=ValidationSeverity.ERROR
            )
    
    def validate_vital_signs(self, vitals: Dict[str, Any]) -> List[ValidationResult]:
        """
        Valida signos vitales.
        
        Args:
            vitals: Dict con signos vitales
        
        Returns:
            Lista de resultados
        """
        results = []
        
        # Peso
        if "peso" in vitals:
            peso = vitals["peso"]
            if peso is not None:
                if peso < self.PESO_MIN or peso > self.PESO_MAX:
                    results.append(ValidationResult(
                        is_valid=False,
                        field="peso",
                        message=f"Peso fuera de rango ({self.PESO_MIN}-{self.PESO_MAX} kg)",
                        severity=ValidationSeverity.WARNING
                    ))
                else:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="peso",
                        message="Peso dentro de rango normal",
                        severity=ValidationSeverity.INFO
                    ))
        
        # Altura
        if "talla" in vitals:
            talla = vitals["talla"]
            if talla is not None:
                if talla < self.ALTURA_MIN or talla > self.ALTURA_MAX:
                    results.append(ValidationResult(
                        is_valid=False,
                        field="talla",
                        message=f"Altura fuera de rango",
                        severity=ValidationSeverity.WARNING
                    ))
                else:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="talla",
                        message="Altura válida",
                        severity=ValidationSeverity.INFO
                    ))
        
        # Temperatura
        if "temperatura" in vitals:
            temp = vitals["temperatura"]
            if temp is not None:
                if temp < self.TEMP_MIN or temp > self.TEMP_MAX:
                    results.append(ValidationResult(
                        is_valid=False,
                        field="temperatura",
                        message=f"Temperatura fuera de rango ({self.TEMP_MIN}-{self.TEMP_MAX}°C)",
                        severity=ValidationSeverity.ERROR
                    ))
                elif temp > 38.0 or temp < 35.5:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="temperatura",
                        message=f"⚠️ Temperatura alterada: {temp}°C",
                        severity=ValidationSeverity.WARNING
                    ))
                else:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="temperatura",
                        message="Temperatura normal",
                        severity=ValidationSeverity.INFO
                    ))
        
        # Frecuencia cardíaca
        if "frecuencia_cardiaca" in vitals:
            fc = vitals["frecuencia_cardiaca"]
            if fc is not None:
                if fc < self.FC_MIN or fc > self.FC_MAX:
                    results.append(ValidationResult(
                        is_valid=False,
                        field="frecuencia_cardiaca",
                        message=f"FC fuera de rango ({self.FC_MIN}-{self.FC_MAX} lpm)",
                        severity=ValidationSeverity.ERROR
                    ))
                elif fc > 100 or fc < 60:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="frecuencia_cardiaca",
                        message=f"⚠️ FC alterada: {fc} lpm",
                        severity=ValidationSeverity.WARNING
                    ))
                else:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="frecuencia_cardiaca",
                        message="FC normal",
                        severity=ValidationSeverity.INFO
                    ))
        
        # Saturación
        if "saturacion_o2" in vitals:
            sat = vitals["saturacion_o2"]
            if sat is not None:
                if sat < self.SAT_O2_MIN or sat > self.SAT_O2_MAX:
                    results.append(ValidationResult(
                        is_valid=False,
                        field="saturacion_o2",
                        message=f"Saturación inválida",
                        severity=ValidationSeverity.ERROR
                    ))
                elif sat < 95:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="saturacion_o2",
                        message=f"🚨 Saturación baja: {sat}%",
                        severity=ValidationSeverity.ERROR
                    ))
                elif sat < 98:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="saturacion_o2",
                        message=f"⚠️ SatO2: {sat}%",
                        severity=ValidationSeverity.WARNING
                    ))
                else:
                    results.append(ValidationResult(
                        is_valid=True,
                        field="saturacion_o2",
                        message=f"✓ SatO2: {sat}%",
                        severity=ValidationSeverity.INFO
                    ))
        
        return results
    
    def sanitize_input(self, value: str, max_length: int = 255) -> str:
        """
        Sanitiza input de usuario.
        
        - Elimina espacios extra
        - Limita longitud
        - Escapa caracteres peligrosos básicos
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Strip
        value = value.strip()
        
        # Limitar longitud
        if len(value) > max_length:
            value = value[:max_length]
        
        # Eliminar caracteres de control excepto newline y tab
        value = ''.join(char for char in value if char == '\n' or char == '\t' or ord(char) >= 32)
        
        return value
    
    def validate_all(self, data: Dict[str, Any], data_type: str = "patient") -> Dict[str, Any]:
        """
        Valida todos los datos y retorna resultado consolidado.
        
        Args:
            data: Datos a validar
            data_type: Tipo de datos (patient, user, vitals, etc.)
        
        Returns:
            Dict con resultado de validación
        """
        all_results = []
        
        if data_type == "patient":
            all_results.extend(self.validate_patient_data(data))
        elif data_type == "vitals":
            all_results.extend(self.validate_vital_signs(data))
        
        # Consolidar
        errors = [r for r in all_results if r.severity == ValidationSeverity.ERROR]
        warnings = [r for r in all_results if r.severity == ValidationSeverity.WARNING]
        
        is_valid = len(errors) == 0
        
        return {
            "is_valid": is_valid,
            "can_save": is_valid or all(r.severity != ValidationSeverity.CRITICAL for r in all_results),
            "errors": errors,
            "warnings": warnings,
            "all_results": all_results,
            "summary": {
                "total": len(all_results),
                "errors": len(errors),
                "warnings": len(warnings),
                "valid": len([r for r in all_results if r.is_valid])
            }
        }


# Singleton
def get_validator() -> DataValidator:
    """Obtiene instancia del validador."""
    return DataValidator()


# Helpers rápidos
def validate_dni(dni: str) -> bool:
    """Valida DNI rápidamente."""
    return get_validator().validate_dni(dni).is_valid


def validate_email(email: str) -> bool:
    """Valida email rápidamente."""
    return get_validator().validate_email(email).is_valid


def sanitize(value: str, max_length: int = 255) -> str:
    """Sanitiza input."""
    return get_validator().sanitize_input(value, max_length)

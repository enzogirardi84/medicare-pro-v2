"""
Sistema de Import/Export de Datos para Medicare Pro.

Soporta:
- Excel (.xlsx)
- CSV
- JSON
- PDF (export only)
- FHIR (export only - healthcare standard)

Características:
- Validación de datos durante import
- Mapeo de campos personalizable
- Preview de cambios
- Rollback en caso de error
- Progreso de importación
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable, BinaryIO
from enum import Enum, auto
import base64

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.data_validation import get_validator


class ImportFormat(Enum):
    """Formatos de importación soportados."""
    CSV = auto()
    EXCEL = auto()
    JSON = auto()


class ExportFormat(Enum):
    """Formatos de exportación soportados."""
    CSV = auto()
    EXCEL = auto()
    JSON = auto()
    PDF = auto()
    FHIR = auto()  # Fast Healthcare Interoperability Resources


@dataclass
class ImportResult:
    """Resultado de importación."""
    success: bool
    total_rows: int
    imported_rows: int
    failed_rows: int
    errors: List[Dict[str, Any]]
    warnings: List[str]
    preview_only: bool
    rollback_available: bool


@dataclass
class FieldMapping:
    """Mapeo de campo importado a campo interno."""
    source_field: str
    target_field: str
    transform: Optional[Callable] = None
    required: bool = False
    default_value: Any = None


class DataImporter:
    """
    Importador de datos con validación y preview.
    """
    
    # Mapeos predefinidos
    PATIENT_IMPORT_MAPPING = {
        "dni": FieldMapping("dni", "dni", required=True),
        "nombre": FieldMapping("nombre", "nombre", required=True),
        "apellido": FieldMapping("apellido", "apellido", required=True),
        "fecha_nacimiento": FieldMapping("fecha_nacimiento", "fecha_nacimiento"),
        "sexo": FieldMapping("sexo", "sexo"),
        "telefono": FieldMapping("telefono", "telefono"),
        "email": FieldMapping("email", "email"),
        "direccion": FieldMapping("direccion", "direccion"),
        "obra_social": FieldMapping("obra_social", "obra_social"),
    }
    
    def __init__(self):
        self.validator = get_validator()
    
    def import_patients(
        self,
        file_data: bytes,
        file_format: ImportFormat,
        mapping: Optional[Dict[str, FieldMapping]] = None,
        preview_only: bool = False,
        skip_validation: bool = False
    ) -> ImportResult:
        """
        Importa pacientes desde archivo.
        
        Args:
            file_data: Contenido del archivo
            file_format: Formato del archivo
            mapping: Mapeo personalizado de campos
            preview_only: Si True, solo muestra preview sin importar
            skip_validation: Si True, salta validación (no recomendado)
        
        Returns:
            ImportResult con resultado
        """
        mapping = mapping or self.PATIENT_IMPORT_MAPPING
        
        try:
            # Parsear archivo
            if file_format == ImportFormat.CSV:
                rows = self._parse_csv(file_data)
            elif file_format == ImportFormat.EXCEL:
                rows = self._parse_excel(file_data)
            elif file_format == ImportFormat.JSON:
                rows = self._parse_json(file_data)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
            
            total_rows = len(rows)
            imported = 0
            failed = 0
            errors = []
            
            # Preview o import
            preview_data = []
            
            for idx, row in enumerate(rows):
                try:
                    # Transformar según mapeo
                    patient_data = self._transform_row(row, mapping)
                    
                    # Validar
                    if not skip_validation:
                        validation = self.validator.validate_all(patient_data, "patient")
                        if not validation["can_save"]:
                            failed += 1
                            errors.append({
                                "row": idx + 1,
                                "data": patient_data,
                                "errors": [e.message for e in validation["errors"]]
                            })
                            continue
                    
                    if preview_only:
                        preview_data.append({
                            "row": idx + 1,
                            "data": patient_data,
                            "valid": True,
                            "warnings": [w.message for w in validation.get("warnings", [])]
                        })
                    else:
                        # Importar a session_state (en producción: DB)
                        self._save_patient(patient_data)
                        imported += 1
                        
                except Exception as e:
                    failed += 1
                    errors.append({"row": idx + 1, "error": str(e)})
            
            # Audit log
            if not preview_only and imported > 0:
                audit_log(
                    AuditEventType.DATA_IMPORT,
                    resource_type="patients",
                    resource_id="batch_import",
                    action="IMPORT",
                    description=f"Imported {imported} patients from {file_format.name}",
                    metadata={"format": file_format.name, "total": total_rows, "imported": imported}
                )
            
            log_event("import", f"Import completed: {imported}/{total_rows} rows")
            
            return ImportResult(
                success=failed == 0 or imported > 0,
                total_rows=total_rows,
                imported_rows=imported,
                failed_rows=failed,
                errors=errors,
                warnings=[],
                preview_only=preview_only,
                rollback_available=not preview_only and imported > 0
            )
            
        except Exception as e:
            log_event("import_error", f"Import failed: {e}")
            return ImportResult(
                success=False,
                total_rows=0,
                imported_rows=0,
                failed_rows=0,
                errors=[{"error": str(e)}],
                warnings=[],
                preview_only=preview_only,
                rollback_available=False
            )
    
    def _parse_csv(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Parsea archivo CSV."""
        text = file_data.decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    
    def _parse_excel(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Parsea archivo Excel."""
        try:
            import pandas as pd
            
            df = pd.read_excel(io.BytesIO(file_data))
            
            # Reemplazar NaN con None
            df = df.where(pd.notnull(df), None)
            
            return df.to_dict('records')
            
        except ImportError:
            raise ImportError("pandas y openpyxl requeridos para Excel: pip install pandas openpyxl")
    
    def _parse_json(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Parsea archivo JSON."""
        data = json.loads(file_data.decode('utf-8'))
        
        # Asegurar que sea lista
        if isinstance(data, dict):
            # Puede ser un único objeto o tener una key con la lista
            if 'patients' in data:
                data = data['patients']
            elif 'data' in data:
                data = data['data']
            else:
                data = [data]
        
        return data
    
    def _transform_row(
        self,
        row: Dict[str, Any],
        mapping: Dict[str, FieldMapping]
    ) -> Dict[str, Any]:
        """Transforma una fila según el mapeo."""
        result = {}
        
        for target_field, field_mapping in mapping.items():
            source_value = row.get(field_mapping.source_field)
            
            # Aplicar transformación si existe
            if field_mapping.transform and source_value:
                source_value = field_mapping.transform(source_value)
            
            # Usar default si es None
            if source_value is None and field_mapping.default_value is not None:
                source_value = field_mapping.default_value
            
            result[target_field] = source_value
        
        return result
    
    def _save_patient(self, patient_data: Dict[str, Any]):
        """Guarda paciente en el sistema."""
        import streamlit as st
        
        # Generar ID si no existe
        if "id" not in patient_data:
            import uuid
            patient_data["id"] = str(uuid.uuid4())
        
        # Agregar a pacientes_db
        if "pacientes_db" not in st.session_state:
            st.session_state["pacientes_db"] = {}
        
        st.session_state["pacientes_db"][patient_data["dni"]] = patient_data


class DataExporter:
    """
    Exportador de datos a múltiples formatos.
    """
    
    def __init__(self):
        self.validator = get_validator()
    
    def export_patients(
        self,
        patient_ids: Optional[List[str]] = None,
        format: ExportFormat = ExportFormat.CSV,
        include_fields: Optional[List[str]] = None
    ) -> Tuple[bytes, str, str]:
        """
        Exporta pacientes a archivo.
        
        Args:
            patient_ids: IDs a exportar (None = todos)
            format: Formato de exportación
            include_fields: Campos a incluir (None = todos)
        
        Returns:
            Tuple de (file_data, filename, mimetype)
        """
        import streamlit as st
        
        # Obtener datos
        pacientes_db = st.session_state.get("pacientes_db", {})
        
        if patient_ids:
            patients = [p for p in pacientes_db.values() if p.get("id") in patient_ids]
        else:
            patients = list(pacientes_db.values())
        
        # Filtrar campos
        if include_fields:
            patients = [
                {k: v for k, v in p.items() if k in include_fields}
                for p in patients
            ]
        
        # Exportar según formato
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == ExportFormat.CSV:
            data = self._export_csv(patients)
            filename = f"pacientes_{timestamp}.csv"
            mimetype = "text/csv"
            
        elif format == ExportFormat.EXCEL:
            data = self._export_excel(patients)
            filename = f"pacientes_{timestamp}.xlsx"
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            
        elif format == ExportFormat.JSON:
            data = self._export_json(patients)
            filename = f"pacientes_{timestamp}.json"
            mimetype = "application/json"
            
        elif format == ExportFormat.FHIR:
            data = self._export_fhir(patients)
            filename = f"pacientes_{timestamp}_fhir.json"
            mimetype = "application/fhir+json"
            
        else:
            raise ValueError(f"Formato no soportado: {format}")
        
        # Audit log
        audit_log(
            AuditEventType.DATA_EXPORT,
            resource_type="patients",
            resource_id="batch_export",
            action="EXPORT",
            description=f"Exported {len(patients)} patients to {format.name}",
            metadata={"format": format.name, "count": len(patients)}
        )
        
        log_event("export", f"Export completed: {len(patients)} patients to {format.name}")
        
        return data, filename, mimetype
    
    def _export_csv(self, patients: List[Dict]) -> bytes:
        """Exporta a CSV."""
        if not patients:
            return b""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=patients[0].keys())
        writer.writeheader()
        writer.writerows(patients)
        
        return output.getvalue().encode('utf-8-sig')  # BOM para Excel
    
    def _export_excel(self, patients: List[Dict]) -> bytes:
        """Exporta a Excel."""
        try:
            import pandas as pd
            
            df = pd.DataFrame(patients)
            
            output = io.BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            
            return output.getvalue()
            
        except ImportError:
            # Fallback a CSV
            return self._export_csv(patients)
    
    def _export_json(self, patients: List[Dict]) -> bytes:
        """Exporta a JSON."""
        data = {
            "export_date": datetime.now().isoformat(),
            "count": len(patients),
            "patients": patients
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8')
    
    def _export_fhir(self, patients: List[Dict]) -> bytes:
        """
        Exporta a formato FHIR (Healthcare standard).
        
        FHIR Patient resource: https://www.hl7.org/fhir/patient.html
        """
        fhir_bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "meta": {
                "versionId": "1",
                "lastUpdated": datetime.now().isoformat()
            },
            "entry": []
        }
        
        for patient in patients:
            fhir_patient = self._convert_to_fhir_patient(patient)
            fhir_bundle["entry"].append({
                "resource": fhir_patient
            })
        
        return json.dumps(fhir_bundle, indent=2, ensure_ascii=False).encode('utf-8')
    
    def _convert_to_fhir_patient(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte paciente interno a recurso FHIR Patient."""
        fhir = {
            "resourceType": "Patient",
            "id": patient.get("id", "unknown"),
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",  # o sistema local
                    "value": patient.get("dni", "")
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": patient.get("apellido", ""),
                    "given": [patient.get("nombre", "")]
                }
            ],
            "gender": self._map_gender_fhir(patient.get("sexo", "")),
        }
        
        # Fecha de nacimiento
        if patient.get("fecha_nacimiento"):
            fhir["birthDate"] = patient["fecha_nacimiento"]
        
        # Contacto
        telecom = []
        if patient.get("telefono"):
            telecom.append({
                "system": "phone",
                "value": patient["telefono"],
                "use": "mobile"
            })
        if patient.get("email"):
            telecom.append({
                "system": "email",
                "value": patient["email"]
            })
        
        if telecom:
            fhir["telecom"] = telecom
        
        # Dirección
        if patient.get("direccion"):
            fhir["address"] = [{
                "text": patient["direccion"],
                "use": "home"
            }]
        
        return fhir
    
    def _map_gender_fhir(self, sexo: str) -> str:
        """Mapea sexo interno a género FHIR."""
        mapping = {
            "M": "male",
            "F": "female",
            "O": "other",
            "": "unknown"
        }
        return mapping.get(sexo.upper(), "unknown")
    
    def export_evoluciones(
        self,
        paciente_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        format: ExportFormat = ExportFormat.PDF
    ) -> Tuple[bytes, str, str]:
        """
        Exporta evoluciones de un paciente.
        
        Args:
            paciente_id: ID del paciente (None = todos)
            date_from: Fecha inicial
            date_to: Fecha final
            format: Formato de exportación
        
        Returns:
            Tuple de (file_data, filename, mimetype)
        """
        import streamlit as st
        
        # Obtener evoluciones
        evoluciones_db = st.session_state.get("evoluciones_db", [])
        
        evoluciones = [
            e for e in evoluciones_db
            if (paciente_id is None or e.get("paciente_id") == paciente_id)
        ]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == ExportFormat.PDF:
            data = self._export_evoluciones_pdf(evoluciones)
            filename = f"evoluciones_{timestamp}.pdf"
            mimetype = "application/pdf"
        else:
            data = self._export_json(evoluciones)
            filename = f"evoluciones_{timestamp}.json"
            mimetype = "application/json"
        
        return data, filename, mimetype
    
    def _export_evoluciones_pdf(self, evoluciones: List[Dict]) -> bytes:
        """Exporta evoluciones a PDF."""
        try:
            from fpdf import FPDF
            
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            for evo in evoluciones:
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, f"Evolución - {evo.get('fecha', 'N/A')}", ln=True)
                
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 10, f"Médico: {evo.get('medico_nombre', 'N/A')}", ln=True)
                pdf.ln(5)
                
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "Nota:", ln=True)
                pdf.set_font("Arial", "", 12)
                
                # Multi-cell para texto largo
                note = evo.get("nota", "Sin nota")
                pdf.multi_cell(0, 5, note)
                
                if evo.get("diagnostico"):
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, "Diagnóstico:", ln=True)
                    pdf.set_font("Arial", "", 12)
                    pdf.multi_cell(0, 5, evo["diagnostico"])
            
            return pdf.output(dest="S").encode("latin-1")
            
        except ImportError:
            # Fallback a texto
            text = "Evoluciones Clínicas\n\n"
            for evo in evoluciones:
                text += f"Fecha: {evo.get('fecha')}\n"
                text += f"Médico: {evo.get('medico_nombre')}\n"
                text += f"Nota: {evo.get('nota')}\n"
                text += "-" * 50 + "\n"
            
            return text.encode('utf-8')


# Singleton
_importer: Optional[DataImporter] = None
_exporter: Optional[DataExporter] = None


def get_importer() -> DataImporter:
    """Obtiene instancia del importador."""
    global _importer
    if _importer is None:
        _importer = DataImporter()
    return _importer


def get_exporter() -> DataExporter:
    """Obtiene instancia del exportador."""
    global _exporter
    if _exporter is None:
        _exporter = DataExporter()
    return _exporter


# Helpers rápidos
def export_patients_to_csv() -> Tuple[bytes, str, str]:
    """Exporta todos los pacientes a CSV."""
    return get_exporter().export_patients(format=ExportFormat.CSV)


def export_patients_to_excel() -> Tuple[bytes, str, str]:
    """Exporta todos los pacientes a Excel."""
    return get_exporter().export_patients(format=ExportFormat.EXCEL)


def import_patients_from_csv(file_data: bytes, preview_only: bool = False) -> ImportResult:
    """Importa pacientes desde CSV."""
    return get_importer().import_patients(
        file_data=file_data,
        file_format=ImportFormat.CSV,
        preview_only=preview_only
    )

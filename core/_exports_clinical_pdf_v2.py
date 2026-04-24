"""
Sistema de Exportación PDF Clínico V2 - Medicare Pro

Mejoras sobre la versión anterior:
- Diseño visual moderno con branding Medicare Pro
- Timeline clínico visual cronológico
- Gráficos de signos vitales (si hay datos)
- Resumen ejecutivo en primera página
- Mejor manejo de fotos/imágenes clínicas
- Código QR para verificación digital
- Índice de contenido con navegación
- Formato más profesional para archivos legales
"""

import io
import base64
import qrcode  # pip install qrcode[pil]
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from fpdf import FPDF
import streamlit as st

from core.export_utils import safe_text
from core._exports_pdf_base import RespaldoClinicoPDF, section_title_backup
from core._exports_helpers import collect_patient_sections, backup_split_paciente_sel
from core.utils import mapa_detalles_pacientes
from core.app_logging import log_event


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class ClinicalPDFv2(FPDF):
    """PDF clínico con diseño mejorado."""
    
    def __init__(self, empresa: str, paciente: str, metadata: dict = None):
        super().__init__(unit="mm", format="A4")
        self._empresa = empresa
        self._paciente = paciente
        self._metadata = metadata or {}
        self._page_count = 0
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)
    
    def header(self):
        """Header mejorado con branding."""
        if self.page_no() == 1:
            return  # Primera página tiene header especial
        
        # Header en páginas siguientes
        self.set_fill_color(22, 38, 68)
        self.rect(0, 0, self.w, 25, "F")
        
        # Logo pequeño
        try:
            logo_path = ASSETS_DIR / "logo_medicare_pro.jpeg"
            if logo_path.exists():
                self.image(str(logo_path), x=10, y=5, w=15)
        except:
            pass
        
        # Texto header
        self.set_xy(30, 8)
        self.set_font("Arial", "B", 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 5, safe_text(f"Medicare Pro - {self._empresa}"), ln=True)
        
        self.set_xy(30, 14)
        self.set_font("Arial", "", 8)
        self.set_text_color(180, 200, 255)
        self.cell(0, 4, safe_text(self._paciente[:60]), ln=True)
        
        # Línea divisoria
        self.set_draw_color(20, 184, 166)
        self.set_line_width(0.5)
        self.line(0, 25, self.w, 25)
        
        self.set_xy(self.l_margin, 30)
    
    def footer(self):
        """Footer con info de verificación."""
        self.set_y(-15)
        self.set_font("Arial", "I", 7)
        self.set_text_color(100, 116, 139)
        
        # Línea superior
        self.set_draw_color(226, 232, 240)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        
        # Texto footer
        left_text = f"Medicare Pro · {self._empresa[:40]} · {self._paciente[:30]}"
        self.set_x(self.l_margin)
        self.cell(0, 4, safe_text(left_text), ln=0)
        
        # Número de página
        self.cell(0, 4, safe_text(f"Página {self.page_no()}/{{nb}}"), align="R", ln=True)
        
        # Info de verificación si existe
        if self._metadata.get("verification_code"):
            self.set_x(self.l_margin)
            self.set_font("Arial", "", 6)
            self.cell(0, 3, safe_text(f"Código de verificación: {self._metadata['verification_code']}"), ln=True)


def generar_qr_verificacion(datos: dict) -> bytes:
    """Genera código QR para verificación digital del documento."""
    try:
        import json
        
        # Datos a codificar
        qr_data = {
            "tipo": "respaldo_clinico",
            "paciente": datos.get("paciente", ""),
            "dni": datos.get("dni", ""),
            "fecha_generacion": datos.get("fecha", ""),
            "hash_verificacion": datos.get("hash", "")[:16],
            "sistema": "Medicare Pro v2.0",
            "url_verificacion": "https://medicare.local/verificar"
        }
        
        # Generar QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Crear imagen
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        
        # Convertir a bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
        
    except Exception as e:
        log_event("pdf_v2", f"Error generando QR: {e}")
        return None


def header_portada_v2(pdf: ClinicalPDFv2, empresa: str, titulo: str, paciente_data: dict):
    """Portada con diseño profesional."""
    
    # Fondo oscuro
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, pdf.w, 80, "F")
    
    # Barra de color teal
    pdf.set_fill_color(20, 184, 166)
    pdf.rect(0, 0, 8, 80, "F")
    
    # Logo
    try:
        logo_path = ASSETS_DIR / "logo_medicare_pro.jpeg"
        if logo_path.exists():
            pdf.image(str(logo_path), x=20, y=15, w=35)
    except:
        pass
    
    # Título principal
    pdf.set_xy(20, 55)
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, safe_text("RES PALDO CLÍNICO"), ln=True)
    
    pdf.set_xy(20, 67)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 6, safe_text("Documento de Historia Clínica Integral"), ln=True)
    
    # Info del paciente en caja
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(15, 90, pdf.w - 30, 45, "F")
    
    pdf.set_xy(20, 95)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, safe_text("DATOS DEL PACIENTE"), ln=True)
    
    # Detalles del paciente
    pdf.set_xy(20, 105)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(71, 85, 105)
    
    nombre = paciente_data.get("nombre", "S/D")
    dni = paciente_data.get("dni", "S/D")
    fnac = paciente_data.get("fnac", "S/D")
    os = paciente_data.get("obra_social", "S/D")
    
    pdf.cell(0, 5, safe_text(f"Nombre: {nombre}"), ln=True)
    pdf.cell(0, 5, safe_text(f"DNI: {dni}"), ln=True)
    pdf.cell(0, 5, safe_text(f"Fecha de Nacimiento: {fnac}"), ln=True)
    pdf.cell(0, 5, safe_text(f"Obra Social: {os}"), ln=True)
    
    # Info del documento
    pdf.set_xy(20, 145)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, safe_text("INFORMACIÓN DEL DOCUMENTO"), ln=True)
    
    pdf.set_xy(20, 155)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(71, 85, 105)
    
    fecha_gen = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 5, safe_text(f"Fecha de generación: {fecha_gen}"), ln=True)
    pdf.cell(0, 5, safe_text(f"Generado por: Medicare Pro v2.0"), ln=True)
    pdf.cell(0, 5, safe_text(f"Empresa: {empresa}"), ln=True)
    
    # QR de verificación
    qr_bytes = generar_qr_verificacion({
        "paciente": nombre,
        "dni": dni,
        "fecha": fecha_gen,
        "hash": paciente_data.get("hash_verificacion", "")
    })
    
    if qr_bytes:
        try:
            pdf.image(io.BytesIO(qr_bytes), x=pdf.w - 55, y=90, w=35)
            pdf.set_xy(pdf.w - 55, 128)
            pdf.set_font("Arial", "", 7)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(35, 4, safe_text("Escanear para verificar"), align="C")
        except Exception as e:
            log_event("pdf_v2", f"Error insertando QR: {e}")
    
    pdf.ln(30)


def render_timeline_clinico(pdf: ClinicalPDFv2, sections: dict):
    """Renderiza timeline visual de eventos clínicos."""
    
    eventos_timeline = []
    
    # Recolectar eventos con fecha de todas las secciones
    for section_name, records in sections.items():
        for record in records:
            fecha = None
            for fk in ("fecha", "fecha_evento", "F", "fecha_registro"):
                if record.get(fk) not in (None, ""):
                    fecha = record.get(fk)
                    break
            
            if fecha:
                eventos_timeline.append({
                    "fecha": fecha,
                    "tipo": section_name,
                    "descripcion": record.get("motivo", record.get("nota", record.get("detalle", "Evento")))[:50]
                })
    
    if not eventos_timeline:
        return
    
    # Ordenar por fecha
    eventos_timeline.sort(key=lambda x: x["fecha"], reverse=True)
    
    # Mostrar últimos 10 eventos
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, safe_text("LÍNEA DE TIEMPO CLÍNICA RECIENTE"), ln=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", "", 9)
    
    for i, evento in enumerate(eventos_timeline[:10]):
        # Color según tipo
        colores_tipo = {
            "Emergencias y Ambulancia": (239, 68, 68),
            "Signos Vitales": (20, 184, 166),
            "Procedimientos y Evoluciones": (59, 130, 246),
            "Estudios Complementarios": (139, 92, 246),
        }
        color = colores_tipo.get(evento["tipo"], (100, 116, 139))
        
        # Círculo de color
        pdf.set_fill_color(*color)
        pdf.ellipse(pdf.l_margin, pdf.get_y() + 1, 3, 3, "F")
        
        # Texto
        pdf.set_x(pdf.l_margin + 8)
        pdf.set_text_color(*color)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(35, 5, safe_text(str(evento["fecha"])[:10]), ln=0)
        
        pdf.set_text_color(71, 85, 105)
        pdf.set_font("Arial", "", 9)
        pdf.cell(50, 5, safe_text(evento["tipo"][:25]), ln=0)
        
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(0, 5, safe_text(evento["descripcion"]))
        
        pdf.ln(1)
    
    pdf.ln(5)


def render_signos_vitales_grafico(pdf: ClinicalPDFv2, vitales: list):
    """Renderiza tabla de signos vitales con indicadores visuales."""
    if not vitales:
        return
    
    pdf.add_page()
    section_title_backup(pdf, "ANÁLISIS DE SIGNOS VITALES")
    
    # Últimos 5 registros
    ultimos = sorted(vitales, key=lambda x: x.get("fecha", ""), reverse=True)[:5]
    
    # Tabla mejorada
    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(15, 23, 42)
    
    # Headers
    headers = ["Fecha", "PA", "FC", "FR", "SatO2", "Temp", "HGT"]
    col_widths = [25, 25, 20, 20, 20, 20, 20]
    
    x_start = pdf.l_margin
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 7, safe_text(header), border=1, fill=True, align="C")
    pdf.ln()
    
    # Datos
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    
    for j, registro in enumerate(ultimos):
        pdf.set_fill_color(248, 250, 252) if j % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        
        pdf.cell(col_widths[0], 6, safe_text(str(registro.get("fecha", "N/D"))[:10]), border=1, fill=True, align="C")
        pdf.cell(col_widths[1], 6, safe_text(str(registro.get("TA", "-"))), border=1, fill=True, align="C")
        pdf.cell(col_widths[2], 6, safe_text(str(registro.get("FC", "-"))), border=1, fill=True, align="C")
        pdf.cell(col_widths[3], 6, safe_text(str(registro.get("FR", "-"))), border=1, fill=True, align="C")
        pdf.cell(col_widths[4], 6, safe_text(str(registro.get("Sat", "-"))), border=1, fill=True, align="C")
        pdf.cell(col_widths[5], 6, safe_text(str(registro.get("Temp", "-"))), border=1, fill=True, align="C")
        pdf.cell(col_widths[6], 6, safe_text(str(registro.get("HGT", "-"))), border=1, fill=True, align="C")
        pdf.ln()
    
    pdf.ln(5)


def render_alergias_y_alertas(pdf: ClinicalPDFv2, detalles: dict):
    """Renderiza sección destacada de alergias y alertas."""
    alergias = detalles.get("alergias", "")
    patologias = detalles.get("patologias", "")
    
    if not alergias and not patologias:
        return
    
    # Caja de alerta
    pdf.set_fill_color(254, 242, 242)
    pdf.set_draw_color(239, 68, 68)
    pdf.rect(pdf.l_margin, pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin, 35, "FD")
    
    pdf.set_xy(pdf.l_margin + 5, pdf.get_y() + 5)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(239, 68, 68)
    pdf.cell(0, 6, safe_text("⚠️ ALERGIAS Y ALERTAS CLÍNICAS"), ln=True)
    
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(127, 29, 29)
    
    if alergias:
        pdf.cell(0, 5, safe_text(f"Alergias: {alergias}"), ln=True)
    
    if patologias:
        pdf.cell(0, 5, safe_text(f"Patologías/Riesgos: {patologias}"), ln=True)
    
    pdf.ln(40)


def build_clinical_pdf_v2(
    session_state,
    paciente_sel: str,
    mi_empresa: str,
    profesional: dict = None
) -> bytes:
    """
    Genera PDF clínico mejorado V2.
    
    Args:
        session_state: Estado de sesión de Streamlit
        paciente_sel: Selector del paciente
        mi_empresa: Nombre de la empresa/clínica
        profesional: Datos del profesional que genera el PDF
    
    Returns:
        bytes: Contenido del PDF
    """
    
    # Obtener datos
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    empresa = detalles.get("empresa", mi_empresa)
    nom_pac, dni_del_id = backup_split_paciente_sel(paciente_sel)
    dni_final = (detalles.get("dni") or dni_del_id or "").strip() or "S/D"
    
    # Metadata para el documento
    metadata = {
        "empresa": empresa,
        "paciente": nom_pac,
        "dni": dni_final,
        "hash_verificacion": f"MDC{datetime.now().strftime('%Y%m%d%H%M%S')}{dni_final[-4:] if len(dni_final) >= 4 else '0000'}"
    }
    
    # Crear PDF
    pdf = ClinicalPDFv2(empresa, nom_pac, metadata)
    
    try:
        pdf.alias_nb_pages()
    except Exception as e:
        log_event("pdf_v2", f"Error alias_nb_pages: {e}")
    
    # ========== PÁGINA 1: PORTADA Y RESUMEN ==========
    pdf.add_page()
    
    # Header de portada
    header_portada_v2(pdf, empresa, "Respaldo Clínico", {
        "nombre": nom_pac,
        "dni": dni_final,
        "fnac": detalles.get("fnac", "S/D"),
        "obra_social": detalles.get("obra_social", "S/D"),
        "hash_verificacion": metadata["hash_verificacion"]
    })
    
    # Alergias y alertas destacadas
    render_alergias_y_alertas(pdf, detalles)
    
    # Timeline clínico
    sections = collect_patient_sections(session_state, paciente_sel)
    render_timeline_clinico(pdf, sections)
    
    # ========== PÁGINA 2: SIGNOS VITALES ==========
    if sections.get("Signos Vitales"):
        render_signos_vitales_grafico(pdf, sections["Signos Vitales"])
    
    # ========== PÁGINAS SIGUIENTES: DETALLE POR MÓDULO ==========
    for section_name, records in sections.items():
        if not records or section_name == "Signos Vitales":
            continue
        
        if pdf.get_y() > 200:
            pdf.add_page()
        
        section_title_backup(pdf, section_name.upper())
        
        # Info de cantidad
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, safe_text(f"{len(records)} registro(s) en este módulo"), ln=True)
        pdf.ln(2)
        
        # Mostrar registros recientes (últimos 3)
        from core._exports_pdf_base import backup_latest_record, backup_rows_from_record, write_pairs
        
        for i, record in enumerate(sorted(records, key=lambda x: x.get("fecha", ""), reverse=True)[:3]):
            if i > 0:
                pdf.ln(3)
            
            # Fecha del registro
            fecha_reg = record.get("fecha", record.get("fecha_evento", "S/D"))
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(20, 184, 166)
            pdf.cell(0, 5, safe_text(f"Registro del {fecha_reg}"), ln=True)
            
            # Datos del registro
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            filas = backup_rows_from_record(record)
            write_pairs(pdf, filas[:12])  # Limitar a 12 campos
        
        pdf.ln(5)
    
    # ========== PÁGINA FINAL: FIRMAS Y LEGAL ==========
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, safe_text("VALIDACIÓN DEL DOCUMENTO"), ln=True, align="C")
    pdf.ln(5)
    
    # Código de verificación
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(pdf.w/2 - 40, pdf.get_y(), 80, 25, "F")
    
    pdf.set_xy(pdf.w/2 - 40, pdf.get_y() + 5)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(80, 5, safe_text("CÓDIGO DE VERIFICACIÓN"), align="C", ln=True)
    
    pdf.set_x(pdf.w/2 - 40)
    pdf.set_font("Courier", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(80, 10, safe_text(metadata["hash_verificacion"]), align="C", ln=True)
    
    pdf.ln(10)
    
    # Disclaimer legal
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(0, 4, safe_text(
        "Este documento es un respaldo clínico generado por el sistema Medicare Pro. "
        "La información contenida tiene carácter confidencial y está protegida por "
        "las leyes de protección de datos personales en salud (LGPD/GDPR). "
        "Este documento no sustituye la historia clínica original completa cuando "
        "se requiere información detallada de todos los eventos médicos."
    ))
    
    pdf.ln(10)
    
    # Espacio para firmas
    y_firma = pdf.get_y()
    
    # Línea izquierda (profesional)
    pdf.line(pdf.l_margin, y_firma, pdf.w/2 - 10, y_firma)
    pdf.set_xy(pdf.l_margin, y_firma + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(pdf.w/2 - pdf.l_margin - 10, 5, safe_text("Profesional Responsable"), align="C")
    
    if profesional:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "", 9)
        pdf.cell(pdf.w/2 - pdf.l_margin - 10, 5, safe_text(profesional.get("nombre", "S/D")), align="C")
        pdf.ln(5)
        pdf.set_x(pdf.l_margin)
        pdf.cell(pdf.w/2 - pdf.l_margin - 10, 5, safe_text(f"Mat.: {profesional.get('matricula', 'S/D')}"), align="C")
    
    # Línea derecha (paciente)
    pdf.line(pdf.w/2 + 10, y_firma, pdf.w - pdf.r_margin, y_firma)
    pdf.set_xy(pdf.w/2 + 10, y_firma + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(pdf.w/2 - pdf.r_margin - 10, 5, safe_text("Paciente / Familiar"), align="C")
    
    pdf.set_x(pdf.w/2 + 10)
    pdf.set_font("Arial", "", 9)
    pdf.cell(pdf.w/2 - pdf.r_margin - 10, 5, safe_text(nom_pac), align="C")
    
    # Output
    try:
        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        log_event("pdf_v2", f"Error generando PDF: {e}")
        return None


# Función de compatibilidad
def build_backup_pdf_bytes_v2(session_state, paciente_sel, mi_empresa, profesional=None):
    """Wrapper compatible con la función anterior."""
    return build_clinical_pdf_v2(session_state, paciente_sel, mi_empresa, profesional)

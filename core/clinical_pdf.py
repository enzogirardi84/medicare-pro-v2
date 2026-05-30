"""Generador de PDFs clinico/legales con firma ECDSA, geofencing y adjuntos.
Diseno corporativo sobrio, optimizado para auditoria de prestadores.
"""
from __future__ import annotations

import base64
import io
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.app_logging import log_event

# Intentar importar reportlab (requerido)
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, Image, NextPageTemplate, PageBreak,
        PageTemplate, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Colores corporativos
COLOR_PRIMARY = "#1e3a5f"
COLOR_SECONDARY = "#2d5a8e"
COLOR_ACCENT = "#0d9488"
COLOR_TEXT = "#1e293b"
COLOR_MUTED = "#64748b"
COLOR_BORDER = "#e2e8f0"
COLOR_BG_LIGHT = "#f8fafc"


# ═══════════════════════════════════════════════════════════════════
# 1. ESTRUCTURAS DE DATOS
# ═══════════════════════════════════════════════════════════════════

class DatosEvolucion:
    """Datos de una evolucion para generar el PDF clinico."""
    def __init__(
        self,
        paciente: str,
        documento_paciente: str = "",
        obra_social: str = "",
        profesional: str = "",
        matricula: str = "",
        fecha_atencion: str = "",
        diagnostico: str = "",
        nota_medica: str = "",
        medicacion: str = "",
        adjuntos: list[dict[str, Any]] | None = None,
        firma_ecdsa: str = "",
        hash_documento: str = "",
        fingerprint_clave: str = "",
        visitas_gps: list[dict[str, Any]] | None = None,
    ):
        self.paciente = paciente
        self.documento_paciente = documento_paciente
        self.obra_social = obra_social
        self.profesional = profesional
        self.matricula = matricula
        self.fecha_atencion = fecha_atencion
        self.diagnostico = diagnostico
        self.nota_medica = nota_medica
        self.medicacion = medicacion
        self.adjuntos = adjuntos or []
        self.firma_ecdsa = firma_ecdsa
        self.hash_documento = hash_documento
        self.fingerprint_clave = fingerprint_clave
        self.visitas_gps = visitas_gps or []


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE RENDERIZADO PDF
# ═══════════════════════════════════════════════════════════════════

class ClinicalPDFGenerator:
    """Genera PDF clinico/legal con formato corporativo, firma ECDSA y adjuntos.

    Uso:
        pdf = ClinicalPDFGenerator()
        pdf_bytes = pdf.generar(datos_evolucion)
        st.download_button("Descargar PDF", data=pdf_bytes, ...)
    """

    PAGE_W, PAGE_H = A4
    MARGIN = 2 * cm
    COLORS = {
        "primary": COLOR_PRIMARY,
        "secondary": COLOR_SECONDARY,
        "accent": COLOR_ACCENT,
        "text": COLOR_TEXT,
        "muted": COLOR_MUTED,
        "border": COLOR_BORDER,
        "bg_light": COLOR_BG_LIGHT,
    }

    def __init__(self):
        if not HAS_REPORTLAB:
            raise ImportError(
                "reportlab no instalado. Ejecutar: pip install reportlab"
            )

    # ── Estilos del documento ──────────────────────────────────

    def _estilos(self) -> dict[str, ParagraphStyle]:
        return {
            "titulo": ParagraphStyle(
                "Titulo", fontSize=18, leading=22, textColor=colors.HexColor(self.COLORS["primary"]),
                spaceAfter=4, fontName="Helvetica-Bold", alignment=TA_LEFT,
            ),
            "subtitulo": ParagraphStyle(
                "Subtitulo", fontSize=10, leading=13, textColor=colors.HexColor(self.COLORS["muted"]),
                spaceAfter=12, fontName="Helvetica",
            ),
            "seccion": ParagraphStyle(
                "Seccion", fontSize=11, leading=14, textColor=colors.HexColor(self.COLORS["primary"]),
                spaceBefore=16, spaceAfter=6, fontName="Helvetica-Bold",
                borderPadding=(0, 0, 4, 0),
            ),
            "cuerpo": ParagraphStyle(
                "Cuerpo", fontSize=9.5, leading=14, textColor=colors.HexColor(self.COLORS["text"]),
                spaceAfter=8, fontName="Helvetica", alignment=TA_JUSTIFY,
            ),
            "label": ParagraphStyle(
                "Label", fontSize=7.5, leading=9, textColor=colors.HexColor(self.COLORS["muted"]),
                fontName="Helvetica-Bold", spaceAfter=1,
            ),
            "valor": ParagraphStyle(
                "Valor", fontSize=9, leading=12, textColor=colors.HexColor(self.COLORS["text"]),
                fontName="Helvetica", spaceAfter=6,
            ),
            "firma_legal": ParagraphStyle(
                "FirmaLegal", fontSize=7.5, leading=10, textColor=colors.HexColor(self.COLORS["muted"]),
                fontName="Helvetica-Oblique", alignment=TA_JUSTIFY,
            ),
            "footer": ParagraphStyle(
                "Footer", fontSize=6.5, leading=8, textColor=colors.HexColor(self.COLORS["muted"]),
                fontName="Helvetica", alignment=TA_CENTER,
            ),
        }

    # ── Cabecera institucional ────────────────────────────────

    def _cabecera(self, story: list, s: dict) -> None:
        story.append(Paragraph("MEDICARE ENTERPRISE PRO", s["titulo"]))
        story.append(Paragraph("Plataforma de Gestion Sanitaria · Documento Clinico Legal", s["subtitulo"]))
        # Linea divisoria
        story.append(Table([[""]], colWidths=[self.PAGE_W - 2 * self.MARGIN],
                           style=TableStyle([
                               ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor(self.COLORS["primary"])),
                           ])))
        story.append(Spacer(1, 12))

    # ── Datos del paciente ────────────────────────────────────

    def _datos_paciente(self, story: list, s: dict, d: DatosEvolucion) -> None:
        story.append(Paragraph("DATOS DEL PACIENTE", s["seccion"]))
        data = [
            [Paragraph("Paciente", s["label"]), Paragraph("Documento", s["label"]),
             Paragraph("Obra Social", s["label"])],
            [Paragraph(d.paciente, s["valor"]), Paragraph(d.documento_paciente, s["valor"]),
             Paragraph(d.obra_social or "No registrada", s["valor"])],
        ]
        t = Table(data, colWidths=[5.5 * cm, 4.5 * cm, 6 * cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("GRID", (0, 0), (-1, 0), 0.5, colors.HexColor(self.COLORS["border"])),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.COLORS["bg_light"])),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

        # Profesional y fecha
        data2 = [
            [Paragraph("Profesional", s["label"]), Paragraph("Matricula", s["label"]),
             Paragraph("Fecha de atencion", s["label"])],
            [Paragraph(d.profesional, s["valor"]), Paragraph(d.matricula or "S/D", s["valor"]),
             Paragraph(d.fecha_atencion, s["valor"])],
        ]
        t2 = Table(data2, colWidths=[5.5 * cm, 4.5 * cm, 6 * cm])
        t2.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("GRID", (0, 0), (-1, 0), 0.5, colors.HexColor(self.COLORS["border"])),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.COLORS["bg_light"])),
        ]))
        story.append(t2)
        story.append(Spacer(1, 8))

    # ── Evolucion medica ──────────────────────────────────────

    def _evolucion(self, story: list, s: dict, d: DatosEvolucion) -> None:
        story.append(Paragraph("EVOLUCION MEDICA", s["seccion"]))

        if d.diagnostico:
            story.append(Paragraph(f"<b>Diagnostico:</b> {d.diagnostico}", s["cuerpo"]))
        if d.nota_medica:
            # Escapar HTML para evitar inyeccion
            nota = d.nota_medica.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(nota, s["cuerpo"]))
        if d.medicacion:
            story.append(Paragraph(f"<b>Medicacion indicada:</b> {d.medicacion}", s["cuerpo"]))
        story.append(Spacer(1, 6))

    # ── Hoja de ruta GPS ──────────────────────────────────────

    def _geofencing(self, story: list, s: dict, d: DatosEvolucion) -> None:
        if not d.visitas_gps:
            return
        story.append(Paragraph("REGISTRO DE VISITA DOMICILIARIA (GEOFENCING)", s["seccion"]))
        data = [[Paragraph("Entrada", s["label"]), Paragraph("Salida", s["label"]),
                 Paragraph("Duracion", s["label"]), Paragraph("Radio", s["label"])]]
        for v in d.visitas_gps:
            entrada = datetime.fromtimestamp(v.get("entrada", 0)).strftime("%H:%M")
            salida = datetime.fromtimestamp(v.get("salida", 0)).strftime("%H:%M")
            duracion = f"{int(v.get('duracion_seg', 0) // 60)} min"
            radio = f"{v.get('radio_metros', 50)} m"
            data.append([
                Paragraph(entrada, s["valor"]),
                Paragraph(salida, s["valor"]),
                Paragraph(duracion, s["valor"]),
                Paragraph(radio, s["valor"]),
            ])
        t = Table(data, colWidths=[3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(self.COLORS["border"])),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.COLORS["bg_light"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    # ── Bloque de firma legal ECDSA ───────────────────────────

    def _bloque_firma(self, story: list, s: dict, d: DatosEvolucion) -> None:
        story.append(Paragraph("CERTIFICACION DIGITAL DE LA PRESTACION", s["seccion"]))
        story.append(Spacer(1, 4))

        # Tabla de metadatos criptograficos
        data = [
            [Paragraph("Fingerprint clave publica (SHA-256)", s["label"]),
             Paragraph(d.fingerprint_clave[:48] + "..." if len(d.fingerprint_clave) > 48 else d.fingerprint_clave, s["valor"])],
            [Paragraph("Hash del documento", s["label"]),
             Paragraph(d.hash_documento[:48] + "..." if len(d.hash_documento) > 48 else d.hash_documento, s["valor"])],
            [Paragraph("Algoritmo de firma", s["label"]),
             Paragraph("ECDSA-SECP256R1 (SHA-256)", s["valor"])],
            [Paragraph("Fecha de firma", s["label"]),
             Paragraph(datetime.now().strftime("%d/%m/%Y %H:%M"), s["valor"])],
        ]
        if d.firma_ecdsa:
            data.append([
                Paragraph("Firma ECDSA (Base64)", s["label"]),
                Paragraph(d.firma_ecdsa[:64] + "...", s["valor"]),
            ])

        t = Table(data, colWidths=[5 * cm, 11 * cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor(self.COLORS["border"])),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(self.COLORS["bg_light"])),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        # Nota legal
        story.append(Paragraph(
            "<b>Validez legal:</b> Este documento esta firmado digitalmente con criptografia asimetrica ECDSA "
            "(SECP256R1). Cualquier modificacion del contenido invalida la firma. La integridad del registro "
            "esta respaldada por un Audit Trail inmutable con encadenamiento de hashes SHA-256, "
            "conforme a los estandares de documentacion clinica y respaldo legal.",
            s["firma_legal"],
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "El codigo de verificacion (fingerprint) permite validar la autoria del profesional "
            "interviniente ante cualquier auditoria.",
            s["firma_legal"],
        ))

    # ── Adjuntos (imagenes) ───────────────────────────────────

    def _adjuntos(self, story: list, d: DatosEvolucion) -> None:
        if not d.adjuntos:
            return
        s = self._estilos()
        story.append(NextPageTemplate("normal"))
        story.append(PageBreak())
        story.append(Paragraph("ANEXO: ESTUDIOS ADJUNTOS", s["seccion"]))
        story.append(Spacer(1, 8))

        max_w = self.PAGE_W - 2 * self.MARGIN - 2 * cm
        for i, adj in enumerate(d.adjuntos):
            ruta = adj.get("ruta", "")
            nombre = adj.get("nombre", f"Adjunto {i + 1}")
            mime = adj.get("mime", "")
            sha = adj.get("sha256", "")

            story.append(Paragraph(f"<b>Documento {i + 1}:</b> {nombre}", s["cuerpo"]))
            if mime:
                story.append(Paragraph(f"Tipo: {mime}", s["firma_legal"]))
            if sha:
                story.append(Paragraph(f"SHA-256: {sha[:32]}...", s["firma_legal"]))
            story.append(Spacer(1, 4))

            # Cargar imagen desde disco de forma segura
            if ruta and os.path.isfile(ruta):
                try:
                    img = Image(ruta, width=min(max_w, 12 * cm),
                                height=min(16 * cm, 20 * cm))
                    story.append(img)
                    story.append(Spacer(1, 8))
                except Exception as exc:
                    log_event("pdf", f"imagen_error:{nombre}:{type(exc).__name__}")
                    story.append(Paragraph(f"<i>Imagen no disponible: {exc}</i>", s["firma_legal"]))
            else:
                story.append(Paragraph("<i>Archivo no disponible en almacenamiento.</i>", s["firma_legal"]))
                story.append(Spacer(1, 8))

    # ── Footer ────────────────────────────────────────────────

    def _footer(self, canvas, doc):
        canvas.saveState()
        s = self._estilos()
        page_num = canvas.getPageNumber()
        text = (
            f"MediCare Enterprise PRO · Documento generado el "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')} · Pagina {page_num}"
        )
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(self.COLORS["muted"]))
        canvas.drawCentredString(self.PAGE_W / 2, 1 * cm, text)
        canvas.restoreState()

    # ── Generacion principal ──────────────────────────────────

    def generar(self, datos: DatosEvolucion) -> bytes:
        """Genera el PDF clinico/legal completo.

        Args:
            datos: Datos estructurados de la evolucion.

        Returns:
            bytes del PDF generado.
        """
        buf = io.BytesIO()
        s = self._estilos()

        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=self.MARGIN, rightMargin=self.MARGIN,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )

        story: list = []
        self._cabecera(story, s)
        self._datos_paciente(story, s, datos)
        self._evolucion(story, s, datos)
        self._geofencing(story, s, datos)
        self._bloque_firma(story, s, datos)
        self._adjuntos(story, datos)

        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# 3. INTEGRACION CON STREAMLIT + AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════

def render_boton_descarga_pdf(
    datos: DatosEvolucion,
    usuario: str,
    key: str = "download_pdf",
) -> None:
    """Renderiza un boton de descarga de PDF en Streamlit con auditoria.

    Args:
        datos: Datos de la evolucion para el PDF.
        usuario: Usuario que descarga (para audit trail).
        key: Key unica del componente Streamlit.
    """
    import streamlit as st

    try:
        with st.spinner("Generando PDF..."):
            generador = ClinicalPDFGenerator()
            pdf_bytes = generador.generar(datos)

        nombre_archivo = (
            f"evolucion_{datos.paciente.replace(' ', '_')[:30]}"
            f"_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )

        st.download_button(
            label="Descargar PDF clinico",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            key=key,
        )

        # Audit trail
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario=usuario,
                accion="EXPORT_PDF",
                recurso=f"evolucion:{datos.paciente}",
                detalle=f"PDF clinico generado y descargado por {usuario}",
            )
            log_event("pdf", f"descarga_ok:{usuario}:{datos.paciente}")
        except Exception as exc:
            log_event("pdf", f"audit_error:{type(exc).__name__}")

    except Exception as exc:
        log_event("pdf", f"generacion_error:{type(exc).__name__}:{exc}")
        st.error("Error al generar el PDF. Verifica que reportlab este instalado.")
        with st.expander("Detalle tecnico"):
            st.code(f"{type(exc).__name__}: {exc}", language="text")

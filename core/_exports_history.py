"""Generación del PDF de Historia Clínica Integral (ReportLab).

Extraído de core/clinical_exports.py.
"""
import io
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

REPORTLAB_DISPONIBLE = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        KeepTogether,
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:
    REPORTLAB_DISPONIBLE = False
    colors = A4 = ParagraphStyle = getSampleStyleSheet = None
    KeepTogether = RLImage = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None

from core.utils import mapa_detalles_pacientes
from core._exports_helpers import collect_patient_sections


def build_history_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    if not REPORTLAB_DISPONIBLE:
        return None

    from datetime import datetime as _dt
    buffer = io.BytesIO()
    _PAGE_W = A4[0] - 60
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=20, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    normal_style = ParagraphStyle("NormalHC", parent=styles["Normal"], fontSize=9, leading=12)
    italic_style = ParagraphStyle("ItalicHC", parent=styles["Normal"], fontSize=9, leading=12, fontName="Helvetica-Oblique")

    def _limpiar(texto):
        if texto in [None, "", "-", "S/D", "Sin datos"]:
            return "-"
        t = str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return t.replace("\n", "<br/>")

    def _sec_hdr(titulo):
        p = Paragraph(
            f'<font color="white"><b>  {_limpiar(titulo).upper()}</b></font>',
            ParagraphStyle("SH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=14),
        )
        t = Table([[p]], colWidths=[_PAGE_W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#162644")),
            ("TOPPADDING", (0, 0), (0, 0), 5),
            ("BOTTOMPADDING", (0, 0), (0, 0), 5),
        ]))
        return t

    def _tabla_sec(titulo, cabeceras, claves, registros, anchos):
        if not registros:
            return
        hdr_s = ParagraphStyle("TH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=1)
        cel_c = ParagraphStyle("TC", parent=styles["Normal"], fontSize=8, alignment=1)
        cel_l = ParagraphStyle("TL", parent=styles["Normal"], fontSize=8, alignment=0)
        datos = [[Paragraph(c, hdr_s) for c in cabeceras]]
        for reg in registros:
            fila = []
            for clave in claves:
                estilo = cel_l if clave in ("med", "insumo", "nota", "observaciones") else cel_c
                fila.append(Paragraph(_limpiar(reg.get(clave, "-")), estilo))
            datos.append(fila)
        t = Table(datos, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(_sec_hdr(titulo))
        elements.append(Spacer(1, 3))
        elements.append(t)
        elements.append(Spacer(1, 10))

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    sections = collect_patient_sections(session_state, paciente_sel)
    nombre_empresa = detalles.get("empresa", mi_empresa)
    nom_pac = paciente_sel.split(" - ")[0] if " - " in paciente_sel else paciente_sel
    fecha_gen = _dt.now().strftime("%d/%m/%Y %H:%M")

    logo_cell = ""
    for ruta in [ASSETS_DIR / "logo_medicare_pro.jpeg", ASSETS_DIR / "logo_medicare_pro.jpg", ASSETS_DIR / "logo_medicare_pro.png"]:
        if ruta.exists() and RLImage is not None:
            try:
                logo_cell = RLImage(str(ruta), width=52, height=52)
            except Exception:
                pass
            break

    hdr_txt = Paragraph(
        f'<font size="14" color="white"><b>{_limpiar(nombre_empresa)}</b></font><br/>'
        f'<font size="9" color="#A0C8FF"><b>HISTORIA CLINICA DIGITAL INTEGRAL</b></font><br/>'
        f'<font size="7" color="#C8D2E6">Paciente: {_limpiar(nom_pac)}   |   Generado: {fecha_gen}</font>',
        ParagraphStyle("HdrTxt", parent=styles["Normal"], leading=18),
    )
    badge_txt = Paragraph(
        '<font size="10" color="white"><b>Historia<br/>Clinica</b></font>',
        ParagraphStyle("Badge", parent=styles["Normal"], alignment=1, leading=14),
    )
    hdr_table = Table([[logo_cell, hdr_txt, badge_txt]], colWidths=[60, 410, 70])
    hdr_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#162644")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#0D5A50")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(hdr_table)
    elements.append(Spacer(1, 10))

    lbl_s = ParagraphStyle("Lbl", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8)
    val_s = ParagraphStyle("Val", parent=styles["Normal"], fontSize=8)

    def _lbl(t):
        return Paragraph(t, lbl_s)

    def _val(t):
        return Paragraph(_limpiar(t), val_s)

    datos_pac = [
        [_lbl("Paciente"), _val(nom_pac), _lbl("DNI"), _val(detalles.get("dni"))],
        [_lbl("Fecha Nac."), _val(detalles.get("fnac")), _lbl("Sexo"), _val(detalles.get("sexo"))],
        [_lbl("Obra Social"), _val(detalles.get("obra_social")), _lbl("Telefono"), _val(detalles.get("telefono"))],
        [_lbl("Domicilio"), _val(detalles.get("direccion")), _lbl("Estado"), _val(detalles.get("estado", "Activo"))],
    ]
    t_pac = Table(datos_pac, colWidths=[70, 180, 70, 220])
    t_pac.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(_sec_hdr("Datos del paciente"))
    elements.append(Spacer(1, 3))
    elements.append(t_pac)

    alergias_txt = detalles.get("alergias", "") or detalles.get("patologias", "")
    if alergias_txt and alergias_txt not in ("-", "Sin datos"):
        alerg_data = [[_lbl("Alergias / Riesgos"), _val(alergias_txt)]]
        t_al = Table(alerg_data, colWidths=[120, 420])
        t_al.setStyle(TableStyle([
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#991B1B")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#FCA5A5")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_al)
    elements.append(Spacer(1, 8))

    diagnosticos_pac = [
        d for d in session_state.get("diagnosticos_db", [])
        if d.get("paciente") == paciente_sel
        and str(d.get("estado", "Activo")).strip().lower() not in ("resuelto", "descartado", "inactivo")
    ]
    if diagnosticos_pac:
        hdr_s2 = ParagraphStyle("TH2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=1)
        cel_c2 = ParagraphStyle("TC2", parent=styles["Normal"], fontSize=8, alignment=1)
        cel_l2 = ParagraphStyle("TL2", parent=styles["Normal"], fontSize=8, alignment=0)
        diag_cabeceras = ["CIE / Código", "Diagnóstico", "Tipo", "Fecha", "Profesional"]
        diag_datos = [[Paragraph(c, hdr_s2) for c in diag_cabeceras]]
        for d in diagnosticos_pac[:30]:
            diag_datos.append([
                Paragraph(_limpiar(d.get("cie") or d.get("codigo", "-")), cel_c2),
                Paragraph(_limpiar(d.get("diagnostico") or d.get("descripcion", "-")), cel_l2),
                Paragraph(_limpiar(d.get("tipo", "-")), cel_c2),
                Paragraph(_limpiar(d.get("fecha", "-")), cel_c2),
                Paragraph(_limpiar(d.get("profesional", "-")), cel_c2),
            ])
        t_diag = Table(diag_datos, colWidths=[70, 230, 70, 80, 90], repeatRows=1)
        t_diag.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(_sec_hdr("Diagnósticos activos"))
        elements.append(Spacer(1, 3))
        elements.append(t_diag)
        elements.append(Spacer(1, 10))

    meds_activas = [
        m for m in sections.get("Plan Terapeutico", [])
        if str(m.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada", "modificada")
    ]
    if meds_activas:
        hdr_sm = ParagraphStyle("THm", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=1)
        cel_cm = ParagraphStyle("TCm", parent=styles["Normal"], fontSize=8, alignment=1)
        cel_lm = ParagraphStyle("TLm", parent=styles["Normal"], fontSize=8, alignment=0)
        med_cab = ["Medicación / Indicación", "Dosis / Posología", "Vía", "Fecha", "Profesional"]
        med_datos = [[Paragraph(c, hdr_sm) for c in med_cab]]
        for m in meds_activas[:20]:
            med_nombre = m.get("med") or m.get("medicamento") or m.get("descripcion") or "-"
            dosis = m.get("dosis") or m.get("posologia") or "-"
            via = m.get("via") or m.get("via_administracion") or "-"
            med_datos.append([
                Paragraph(_limpiar(med_nombre), cel_lm),
                Paragraph(_limpiar(dosis), cel_cm),
                Paragraph(_limpiar(via), cel_cm),
                Paragraph(_limpiar(m.get("fecha", "-")), cel_cm),
                Paragraph(_limpiar(m.get("medico_nombre") or m.get("profesional", "-")), cel_cm),
            ])
        t_meds = Table(med_datos, colWidths=[195, 100, 60, 80, 105], repeatRows=1)
        t_meds.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D5A50")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F0FDF4"), colors.white]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(_sec_hdr("Medicación activa"))
        elements.append(Spacer(1, 3))
        elements.append(t_meds)
        elements.append(Spacer(1, 10))

    _RANGOS_PDF = {
        "FC": (60, 100, 40, 130),
        "FR": (12, 20, 8, 30),
        "Sat": (94, 100, 88, 100),
        "Temp": (36.0, 37.5, 35.0, 39.0),
    }

    def _color_vital(clave, valor):
        r = _RANGOS_PDF.get(clave)
        if r is None:
            return None
        try:
            v = float(str(valor).replace(",", "."))
            if v < r[2] or v > r[3]:
                return colors.HexColor("#FEE2E2")
            if v < r[0] or v > r[1]:
                return colors.HexColor("#FEF9C3")
        except Exception:
            pass
        return None

    vits_recientes = sorted(sections.get("Signos Vitales", []), key=lambda x: x.get("fecha", ""), reverse=True)[:5]
    if vits_recientes:
        hdr_sv = ParagraphStyle("THv", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=1)
        cel_cv = ParagraphStyle("TCv", parent=styles["Normal"], fontSize=8, alignment=1)
        v_cab = ["Fecha", "T.A.", "F.C.", "F.R.", "SpO2", "Temp", "HGT", "Registrado por"]
        v_datos = [[Paragraph(c, hdr_sv) for c in v_cab]]
        colores_fila = {}
        for fi, vr in enumerate(vits_recientes, start=1):
            fila = [Paragraph(_limpiar(vr.get("fecha", "-")), cel_cv)]
            fila.append(Paragraph(_limpiar(vr.get("TA", "-")), cel_cv))
            for clave in ("FC", "FR", "Sat", "Temp", "HGT"):
                val = vr.get(clave, "-")
                fila.append(Paragraph(_limpiar(val), cel_cv))
                c_bg = _color_vital(clave, val)
                if c_bg:
                    col_idx = ("FC", "FR", "Sat", "Temp", "HGT").index(clave) + 2
                    colores_fila[(fi, col_idx)] = c_bg
            fila.append(Paragraph(_limpiar(vr.get("registrado_por") or vr.get("firma", "-")), cel_cv))
            v_datos.append(fila)
        t_vits5 = Table(v_datos, colWidths=[90, 55, 45, 45, 45, 45, 45, 110], repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#162644")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]
        for (fi, ci), bg in colores_fila.items():
            style_cmds.append(("BACKGROUND", (ci, fi), (ci, fi), bg))
        t_vits5.setStyle(TableStyle(style_cmds))
        elements.append(_sec_hdr("Últimos 5 controles de signos vitales"))
        elements.append(Spacer(1, 3))
        elements.append(t_vits5)
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 4))

    registros_clinicos = sections.get("Procedimientos y Evoluciones", []) + sections.get("Enfermeria y Plan de Cuidados", [])
    if registros_clinicos:
        elements.append(_sec_hdr("Evoluciones clinicas y enfermeria"))
        elements.append(Spacer(1, 4))
        for reg in sorted(registros_clinicos, key=lambda x: x.get("fecha", "")):
            fecha = _limpiar(reg.get("fecha", "S/D"))
            firma = _limpiar(reg.get("firma", reg.get("profesional", "S/D")))
            nota = _limpiar(
                reg.get("nota") or reg.get("intervencion") or reg.get("descripcion")
                or reg.get("observaciones") or "Sin detalle"
            )
            bloque = [
                Paragraph(f"<b>{fecha}</b>  |  {firma}", italic_style),
                Spacer(1, 2),
                Paragraph(nota, normal_style),
                Spacer(1, 8),
            ]
            elements.append(KeepTogether(bloque))

    vits = sections.get("Signos Vitales", [])
    _tabla_sec("Signos vitales", ["Fecha", "T.A.", "F.C.", "F.R.", "SatO2", "Temp", "HGT"],
               ["fecha", "TA", "FC", "FR", "Sat", "Temp", "HGT"], vits, [95, 60, 50, 50, 50, 50, 50])

    balances = sections.get("Balance Hidrico", [])
    _tabla_sec("Balance hidrico", ["Fecha", "Turno", "Ingresos", "Egresos", "Balance", "Firma"],
               ["fecha", "turno", "ingresos", "egresos", "balance", "firma"], balances, [90, 90, 60, 60, 65, 100])

    meds = sections.get("Plan Terapeutico", [])
    _tabla_sec("Plan terapeutico", ["Fecha", "Medicacion / Indicacion", "Estado", "Profesional"],
               ["fecha", "med", "estado_receta", "medico_nombre"], meds, [80, 240, 70, 75])

    materiales = sections.get("Materiales Utilizados", [])
    _tabla_sec("Materiales e insumos", ["Fecha", "Insumo / Descripcion", "Cantidad", "Firma"],
               ["fecha", "insumo", "cantidad", "firma"], materiales, [90, 240, 60, 75])

    emergencias = sections.get("Emergencias y Ambulancia", [])
    _tabla_sec("Emergencias y traslados", ["Fecha", "Triage", "Motivo", "Profesional", "Destino"],
               ["fecha_evento", "triage_grado", "motivo", "profesional", "destino"], emergencias, [80, 80, 200, 90, 85])

    estudios = sections.get("Estudios Complementarios", [])
    _tabla_sec("Estudios complementarios", ["Fecha", "Tipo", "Detalle / Informe", "Profesional"],
               ["fecha", "tipo", "detalle", "firma"], estudios, [80, 100, 240, 75])

    pediatria_all = sections.get("Control Pediatrico", [])
    ped_menor = [r for r in pediatria_all if str(r.get("tipo_control", "pediatrico")).lower() != "adulto"]
    ped_adulto = [r for r in pediatria_all if str(r.get("tipo_control", "")).lower() == "adulto"]
    if ped_menor:
        _tabla_sec("Control pediatrico", ["Fecha", "Peso (kg)", "Talla (cm)", "PC (cm)", "IMC", "Percentil", "Profesional"],
                   ["fecha", "peso", "talla", "pc", "imc", "percentil_sug", "firma"],
                   ped_menor, [80, 55, 55, 55, 45, 65, 140])
    if ped_adulto:
        _tabla_sec("Control antropometrico (adulto)", ["Fecha", "Peso (kg)", "Talla (cm)", "IMC", "Clasificacion IMC", "Profesional"],
                   ["fecha", "peso", "talla", "imc", "percentil_sug", "firma"],
                   ped_adulto, [80, 55, 55, 50, 120, 135])

    escalas = sections.get("Escalas Clinicas", [])
    _tabla_sec("Escalas clinicas", ["Fecha", "Escala", "Puntaje", "Interpretacion", "Profesional"],
               ["fecha", "escala", "puntaje", "interpretacion", "profesional"], escalas, [80, 120, 60, 170, 75])

    consentimientos = sections.get("Consentimientos", [])
    _tabla_sec("Consentimientos informados", ["Fecha", "Tipo documento", "Observaciones", "Profesional"],
               ["fecha", "tipo_documento", "observaciones", "profesional"], consentimientos, [80, 140, 225, 75])

    if not (registros_clinicos or vits or balances or meds or materiales or emergencias
            or estudios or pediatria or escalas or consentimientos):
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<i>No hay registros clinicos cargados para este paciente.</i>", normal_style))

    doc.build(elements)
    return buffer.getvalue()

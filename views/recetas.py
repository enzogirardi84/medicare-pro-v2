import base64
import io
import os

import pandas as pd
import streamlit as st
from PIL import Image

from core.clinical_exports import build_prescription_pdf_bytes
from core.database import guardar_datos
from core.utils import ahora, cargar_json_asset, registrar_auditoria_legal

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF

    FPDF_DISPONIBLE = True
except ImportError:
    pass

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def render_recetas(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Prescripcion y administracion de medicamentos</h2>
            <p class="mc-hero-text">La vista combina catalogo guiado, firma profesional y seguimiento de dosis para reducir errores de medicacion y dejar trazabilidad completa.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Catalogo de medicamentos</span>
                <span class="mc-chip">Firma medica</span>
                <span class="mc-chip">Registro de dosis</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = ["Medicamento 1", "Medicamento 2"]

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Menos errores</h4><p>Elegir del catalogo evita cargar nombres mal escritos o presentaciones confusas.</p></div>
            <div class="mc-card"><h4>Receta trazable</h4><p>La prescripcion queda con fecha, medico, matricula y firma digital cuando esta disponible.</p></div>
            <div class="mc-card"><h4>Control diario</h4><p>La sabana muestra rapido si cada dosis fue realizada o quedo pendiente.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Nueva prescripcion medica")
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        med_vademecum = c1.selectbox("Medicamento", ["-- Seleccionar del vademecum --"] + vademecum_base)
        med_manual = c2.text_input("O escribir manualmente")
        col3, col4, col5 = st.columns([2, 2, 1])
        via = col3.selectbox(
            "Via de administracion",
            ["Via Oral", "Via Endovenosa", "Via Intramuscular", "Via Subcutanea", "Via Topica", "Via Inhalatoria", "Otra"],
        )
        frecuencia = col4.selectbox(
            "Frecuencia",
            [
                "Cada 1 hora",
                "Cada 2 horas",
                "Cada 4 horas",
                "Cada 6 horas",
                "Cada 8 horas",
                "Cada 12 horas",
                "Cada 24 horas",
                "Dosis unica",
                "Segun necesidad",
            ],
        )
        dias = col5.number_input("Dias", min_value=1, max_value=90, value=7)
        col_m1, col_m2 = st.columns(2)
        medico_nombre = col_m1.text_input("Nombre del medico", value=user.get("nombre", ""))
        medico_matricula = col_m2.text_input("Matricula profesional")

        firma_canvas = None
        if CANVAS_DISPONIBLE and st.checkbox("Cargar firma digital", value=False):
            firma_canvas = st_canvas(
                key="firma_receta_activa",
                background_color="#ffffff",
                height=140,
                drawing_mode="freedraw",
                stroke_width=3,
                stroke_color="#000000",
                display_toolbar=True,
            )

        if st.button("Guardar prescripcion medica", use_container_width=True, type="primary"):
            med_final = med_manual.strip().title() if med_manual.strip() else med_vademecum
            if med_final and med_final != "-- Seleccionar del vademecum --":
                if not medico_matricula.strip():
                    st.error("Debe ingresar la matricula del medico.")
                else:
                    firma_b64 = ""
                    if CANVAS_DISPONIBLE and firma_canvas is not None and firma_canvas.image_data is not None:
                        img = Image.fromarray(firma_canvas.image_data.astype("uint8"), "RGBA")
                        fondo = Image.new("RGB", img.size, (255, 255, 255))
                        fondo.paste(img, mask=img.split()[-1])
                        buf = io.BytesIO()
                        fondo.save(buf, format="JPEG", optimize=True, quality=65)
                        firma_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

                    texto_receta = f"{med_final} | Via: {via} | {frecuencia} | Durante {dias} dias"
                    st.session_state["indicaciones_db"].append(
                        {
                            "paciente": paciente_sel,
                            "med": texto_receta,
                            "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "dias_duracion": dias,
                            "medico_nombre": medico_nombre.strip(),
                            "medico_matricula": medico_matricula.strip(),
                            "firma_b64": firma_b64,
                            "firmado_por": user["nombre"],
                            "estado_clinico": "Activa",
                            "estado_receta": "Activa",
                            "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "profesional_estado": user["nombre"],
                            "matricula_estado": medico_matricula.strip(),
                        }
                    )
                    registrar_auditoria_legal(
                        "Medicacion",
                        paciente_sel,
                        "Indicacion medica registrada",
                        medico_nombre.strip() or user.get("nombre", ""),
                        medico_matricula.strip(),
                        texto_receta,
                    )
                    guardar_datos()
                    st.success(f"Prescripcion de {med_final} guardada con firma medica.")
                    st.rerun()

    st.divider()
    recs_todas = [r for r in st.session_state.get("indicaciones_db", []) if r.get("paciente") == paciente_sel]
    recs_activas = [r for r in recs_todas if r.get("estado_receta", "Activa") == "Activa"]

    if recs_activas:
        st.markdown("#### Administracion de hoy")
        fecha_hoy = ahora().strftime("%d/%m/%Y")
        admin_hoy = [
            a
            for a in st.session_state.get("administracion_med_db", [])
            if a.get("paciente") == paciente_sel and a.get("fecha") == fecha_hoy
        ]
        mostrar_sabana = st.checkbox("Mostrar sabana completa de 24 horas", value=False)

        table_data = []
        horas = [f"{h:02d}:00" for h in range(24 if mostrar_sabana else 12)]
        for r in recs_activas[:30]:
            partes = r["med"].split(" | ")
            nombre = partes[0].strip()
            via_texto = partes[1].replace("Via: ", "") if len(partes) > 1 else ""
            freq = partes[2] if len(partes) > 2 else ""
            fila = {"Medicamento": nombre, "Via": via_texto, "Frecuencia": freq}
            for h in horas:
                realizada = any(a.get("med") == nombre and a.get("hora", "").startswith(h[:2]) for a in admin_hoy)
                fila[h] = "OK" if realizada else "-"
            table_data.append(fila)
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        st.caption("OK = administrado | - = pendiente")

        with st.form("form_registro_dosis", clear_on_submit=True):
            meds_activas_nombres = [r["med"].split(" |")[0].strip() for r in recs_activas]
            c_med, c_hora = st.columns([2, 1])
            med_sel = c_med.selectbox("Medicacion a registrar", meds_activas_nombres)
            opciones_hora = [f"{i:02d}:00" for i in range(24)]
            hora_actual_str = f"{ahora().hour:02d}:00"
            idx_hora = opciones_hora.index(hora_actual_str) if hora_actual_str in opciones_hora else 0
            hora_sel = c_hora.selectbox("Hora de la dosis", opciones_hora, index=idx_hora)
            estado_sel = st.radio("Estado", ["Realizada", "No realizada / Suspendida"], horizontal=True)
            justificacion = st.text_input("Justificacion clinica")
            if st.form_submit_button("Guardar registro", use_container_width=True):
                if "No realizada" in estado_sel and not justificacion.strip():
                    st.error("Es obligatorio justificar por que no se administro la dosis.")
                else:
                    st.session_state["administracion_med_db"] = [
                        a
                        for a in st.session_state.get("administracion_med_db", [])
                        if not (
                            a.get("paciente") == paciente_sel
                            and a.get("fecha") == fecha_hoy
                            and a.get("med") == med_sel
                            and a.get("hora") == hora_sel
                        )
                    ]
                    st.session_state["administracion_med_db"].append(
                        {
                            "paciente": paciente_sel,
                            "med": med_sel,
                            "fecha": fecha_hoy,
                            "hora": hora_sel,
                            "estado": estado_sel,
                            "motivo": justificacion.strip() if "No realizada" in estado_sel else "",
                            "firma": user["nombre"],
                        }
                    )
                    guardar_datos()
                    st.success(f"Registro guardado para las {hora_sel}.")
                    st.rerun()

        st.divider()
        c_ed1, c_ed2 = st.columns([3, 2])
        opciones_recetas = [f"[{r.get('fecha', '')}] {r.get('med', '')}" for r in recs_activas]
        receta_seleccionada = c_ed1.selectbox("Seleccionar indicacion", opciones_recetas)
        accion_receta = c_ed2.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
        nuevo_texto_receta = ""
        motivo_cambio = st.text_input("Motivo medico / legal del cambio", key="motivo_cambio_receta")
        if accion_receta == "Editar indicacion" and receta_seleccionada:
            nuevo_texto_receta = st.text_input(
                "Modificar detalle",
                value=receta_seleccionada.split("] ", 1)[1] if "] " in receta_seleccionada else receta_seleccionada,
            )
        if st.button("Aplicar cambios", use_container_width=True):
            for r in st.session_state["indicaciones_db"]:
                if r["paciente"] == paciente_sel and f"[{r.get('fecha', '')}] {r.get('med', '')}" == receta_seleccionada:
                    if accion_receta == "Suspender / Anular":
                        r["estado_receta"] = "Suspendida"
                        r["estado_clinico"] = "Suspendida"
                        r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                        r["fecha_estado"] = r["fecha_suspension"]
                        r["profesional_estado"] = user["nombre"]
                        r["matricula_estado"] = user.get("matricula", "")
                        r["motivo_estado"] = motivo_cambio.strip()
                        registrar_auditoria_legal(
                            "Medicacion",
                            paciente_sel,
                            "Indicacion suspendida",
                            user.get("nombre", ""),
                            user.get("matricula", ""),
                            f"{r.get('med', '')} | Motivo: {motivo_cambio.strip()}",
                        )
                    elif accion_receta == "Editar indicacion" and nuevo_texto_receta:
                        r["estado_receta"] = "Modificada"
                        r["estado_clinico"] = "Modificada"
                        r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                        r["fecha_estado"] = r["fecha_suspension"]
                        r["profesional_estado"] = user["nombre"]
                        r["matricula_estado"] = user.get("matricula", "")
                        r["motivo_estado"] = motivo_cambio.strip()
                        st.session_state["indicaciones_db"].append(
                            {
                                "paciente": paciente_sel,
                                "med": nuevo_texto_receta,
                                "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "dias_duracion": r.get("dias_duracion", 7),
                                "medico_nombre": r.get("medico_nombre", ""),
                                "medico_matricula": r.get("medico_matricula", ""),
                                "firma_b64": r.get("firma_b64", ""),
                                "firmado_por": user["nombre"],
                                "estado_clinico": "Activa",
                                "estado_receta": "Activa",
                                "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "profesional_estado": user["nombre"],
                                "matricula_estado": user.get("matricula", ""),
                                "motivo_estado": f"Reemplaza indicacion previa. Motivo: {motivo_cambio.strip()}".strip(),
                            }
                        )
                        registrar_auditoria_legal(
                            "Medicacion",
                            paciente_sel,
                            "Indicacion modificada",
                            user.get("nombre", ""),
                            user.get("matricula", ""),
                            f"Anterior: {r.get('med', '')} | Nueva: {nuevo_texto_receta} | Motivo: {motivo_cambio.strip()}",
                        )
                    break
            guardar_datos()
            st.rerun()
    else:
        st.info("Aun no hay medicacion activa para este paciente.")

    st.divider()
    if recs_todas:
        st.markdown("#### Historial completo de prescripciones")

        with st.container(height=450):
            for idx, r in enumerate(reversed(recs_todas[-30:])):
                with st.container(border=True):
                    c_info, c_btn = st.columns([3, 1])
                    estado_actual = r.get("estado_receta", "Activa")
                    c_info.markdown(f"**{r.get('fecha', '-')}**")
                    c_info.markdown(
                        f"**Indicado por:** {r.get('medico_nombre', '-')} | **Matricula:** {r.get('medico_matricula', '-')}"
                    )
                    c_info.markdown(f"*{r.get('med', '')}*")
                    if r.get("firma_b64"):
                        try:
                            c_info.image(base64.b64decode(r["firma_b64"]), caption="Firma medica registrada", width=200)
                        except Exception:
                            pass
                    if estado_actual != "Activa":
                        c_info.error(
                            f"Estado: {estado_actual.upper()} | Fecha: {r.get('fecha_suspension', 'S/D')} | "
                            f"Profesional: {r.get('profesional_estado', 'S/D')}"
                        )
                        if r.get("motivo_estado"):
                            c_info.caption(f"Motivo: {r.get('motivo_estado')}")
                    if FPDF_DISPONIBLE and st.checkbox("PDF", key=f"pdf_rec_{idx}", value=False):
                        pdf_bytes = build_prescription_pdf_bytes(
                            st.session_state,
                            paciente_sel,
                            mi_empresa,
                            r,
                            {"nombre": r.get("medico_nombre", user.get("nombre", "")), "matricula": r.get("medico_matricula", "")},
                        )
                        estado_arch = (r.get("estado_receta") or "Activa").replace(" ", "_")
                        nombre_arch = (
                            f"Receta_Legal_{paciente_sel.split(' - ')[0].replace(' ', '_')}_"
                            f"{r.get('fecha', '')[:10].replace('/','')}_{estado_arch}.pdf"
                        )
                        c_btn.download_button(
                            "Descargar PDF legal",
                            data=pdf_bytes,
                            file_name=nombre_arch,
                            mime="application/pdf",
                            key=f"pdf_rec_btn_{idx}",
                            use_container_width=True,
                        )

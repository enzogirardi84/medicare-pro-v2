import pandas as pd
import streamlit as st

from core.export_utils import dataframe_csv_bytes, sanitize_filename_component
from core.utils import contenedores_responsivos, modo_celular_viejo_activo, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_auditoria_legal(mi_empresa, user):
    modo_liviano = modo_celular_viejo_activo()
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Auditoria legal central</h2>
            <p class="mc-hero-text">Concentra eventos clinicos y documentales con valor legal: medicacion, consentimientos, emergencias, escalas y cuidados.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Trazabilidad</span>
                <span class="mc-chip">Actor y matricula</span>
                <span class="mc-chip">Paciente</span>
                <span class="mc-chip">Fecha y hora</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = pd.DataFrame(st.session_state.get("auditoria_legal_db", []))
    if df.empty:
        st.info("Todavia no hay eventos legales registrados.")
        return

    if modo_liviano:
        st.info("Modo celular viejo activo: filtros y tabla en formato mas liviano para leer auditoria desde el telefono.")

    df = df.copy()
    if "fecha_iso" in df.columns:
        df["fecha_orden"] = pd.to_datetime(df["fecha_iso"], errors="coerce")
    elif "fecha" in df.columns:
        df["fecha_orden"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
    else:
        df["fecha_orden"] = pd.NaT

    filtro = st.text_input("Buscar por paciente, accion, actor, login o detalle")
    if filtro:
        mask = df.astype(str).apply(lambda x: x.str.contains(filtro, case=False, na=False)).any(axis=1)
        df = df[mask]

    col_f1, col_f2, col_f3, col_f4 = contenedores_responsivos(4, modo_liviano)
    if "paciente" in df.columns:
        pacientes = ["Todos"] + sorted([x for x in df["paciente"].dropna().astype(str).unique().tolist() if x])
        paciente_sel = col_f1.selectbox("Paciente", pacientes)
        if paciente_sel != "Todos":
            df = df[df["paciente"] == paciente_sel]

    if "modulo" in df.columns:
        modulos = ["Todos"] + sorted([x for x in df["modulo"].dropna().astype(str).unique().tolist() if x])
        modulo_sel = col_f2.selectbox("Modulo", modulos)
        if modulo_sel != "Todos":
            df = df[df["modulo"] == modulo_sel]

    if "criticidad" in df.columns:
        criticidades = ["Todas"] + sorted([x for x in df["criticidad"].dropna().astype(str).unique().tolist() if x])
        criticidad_sel = col_f3.selectbox("Criticidad", criticidades)
        if criticidad_sel != "Todas":
            df = df[df["criticidad"] == criticidad_sel]

    if "actor_rol" in df.columns:
        roles = ["Todos"] + sorted([x for x in df["actor_rol"].dropna().astype(str).unique().tolist() if x])
        rol_sel = col_f4.selectbox("Rol actor", roles)
        if rol_sel != "Todos":
            df = df[df["actor_rol"] == rol_sel]

    col_f5, col_f6 = contenedores_responsivos(2, modo_liviano)
    if "actor_login" in df.columns:
        actores_login = ["Todos"] + sorted([x for x in df["actor_login"].dropna().astype(str).unique().tolist() if x])
        actor_login_sel = col_f5.selectbox("Login actor", actores_login)
        if actor_login_sel != "Todos":
            df = df[df["actor_login"] == actor_login_sel]

    if "empresa" in df.columns:
        empresas = ["Todas"] + sorted([x for x in df["empresa"].dropna().astype(str).unique().tolist() if x])
        empresa_sel = col_f6.selectbox("Empresa evento", empresas)
        if empresa_sel != "Todas":
            df = df[df["empresa"] == empresa_sel]

    if "fecha_orden" in df.columns:
        df = df.sort_values(["fecha_orden", "fecha"], ascending=[False, False], na_position="last")

    col_m1, col_m2, col_m3, col_m4 = contenedores_responsivos(4, modo_liviano)
    col_m1.metric("Eventos filtrados", len(df))
    eventos_criticos = 0
    if "criticidad" in df.columns and not df.empty:
        eventos_criticos = int(df["criticidad"].astype(str).str.lower().isin(["alta", "critica"]).sum())
    col_m2.metric("Altos / criticos", eventos_criticos)
    col_m3.metric("Pacientes", df["paciente"].nunique() if "paciente" in df.columns and not df.empty else 0)
    col_m4.metric("Actores", df["actor_login"].nunique() if "actor_login" in df.columns and not df.empty else 0)

    columnas_prioritarias = [
        "fecha",
        "criticidad",
        "modulo",
        "tipo_evento",
        "accion",
        "paciente",
        "actor",
        "actor_login",
        "actor_rol",
        "actor_perfil",
        "detalle",
        "referencia",
        "objetivo_login",
        "objetivo_rol",
        "empresa",
        "audit_id",
    ]
    columnas_visibles = [col for col in columnas_prioritarias if col in df.columns]
    df_mostrar = df[columnas_visibles].copy()
    df_mostrar = df_mostrar.rename(
        columns={
            "fecha": "Fecha",
            "criticidad": "Criticidad",
            "modulo": "Modulo",
            "tipo_evento": "Tipo evento",
            "accion": "Accion",
            "paciente": "Paciente",
            "actor": "Actor",
            "actor_login": "Login actor",
            "actor_rol": "Rol actor",
            "actor_perfil": "Perfil actor",
            "detalle": "Detalle",
            "referencia": "Referencia",
            "objetivo_login": "Objetivo login",
            "objetivo_rol": "Objetivo rol",
            "empresa": "Empresa",
            "audit_id": "Audit ID",
        }
    )

    limite = seleccionar_limite_registros(
        "Eventos a mostrar",
        len(df),
        key=f"auditoria_legal_{mi_empresa}_{user.get('nombre', '')}",
        default=50,
    )
    mostrar_dataframe_con_scroll(df_mostrar.head(limite), height=460)

    csv_data = dataframe_csv_bytes(df.drop(columns=["fecha_orden"], errors="ignore"))
    st.download_button(
        "Descargar CSV auditoria legal",
        data=csv_data,
        file_name=f"auditoria_legal_{sanitize_filename_component(mi_empresa, 'empresa')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

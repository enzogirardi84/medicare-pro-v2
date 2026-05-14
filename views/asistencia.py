from core.alert_toasts import queue_toast
from datetime import datetime
from html import escape

import streamlit as st

from core.database import guardar_datos
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_asistencia(mi_empresa, user):
    emp_e = escape(str(mi_empresa or ""))
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Asistencia en vivo</h2>
            <p class="mc-hero-text">Quien esta en domicilio hoy segun fichadas GPS para {emp_e}. Listado liviano sin historiales infinitos.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Fichadas del dia</span>
                <span class="mc-chip">Guardia activa</span>
                <span class="mc-chip">Forzar salida</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Hoy", "Solo fichadas del dia actual de tu clinica."),
            ("Guardia abierta", "Ultima LLEGADA sin SALIDA: se muestra como en domicilio."),
            ("Auditoria", "Tabla liviana de movimientos con limite de filas."),
        ]
    )
    st.info(
        "Monitorea en tiempo real a los profesionales que se encuentran trabajando en domicilio "
        "sin cargar historiales enormes de una sola vez."
    )
    st.caption(
        "**Forzar salida** cierra la guardia si olvidaron fichar salida en **Visitas**. La lista inferior es la pista de auditoria del dia."
    )

    hoy_str = ahora().strftime("%d/%m/%Y")
    chks_hoy = [
        c
        for c in st.session_state.get("checkin_db", [])
        if c.get("fecha_hora", "").startswith(hoy_str) and c.get("empresa") == mi_empresa
    ]

    estado_profesionales = {}
    for chk in chks_hoy:
        profesional = chk["profesional"]
        paciente = chk["paciente"]
        try:
            dt = datetime.strptime(chk["fecha_hora"], "%d/%m/%Y %H:%M:%S")
        except Exception:
            dt = datetime.strptime(chk["fecha_hora"], "%d/%m/%Y %H:%M")

        if "LLEGADA" in chk["tipo"]:
            estado_profesionales[profesional] = {"estado": "En Guardia", "llegada": dt, "paciente": paciente}
        elif "SALIDA" in chk["tipo"]:
            estado_profesionales[profesional] = {"estado": "Fuera", "llegada": None, "paciente": None}

    activos = {k: v for k, v in estado_profesionales.items() if v["estado"] == "En Guardia"}

    if activos:
        st.markdown("#### Profesionales actualmente en domicilio")
        with lista_plegable("En domicilio ahora", count=len(activos), expanded=True, height=380):
            for profesional, data in activos.items():
                with st.container(border=True):
                    col_info, col_btn = st.columns([3, 1])
                    dt_llegada = data["llegada"]
                    duracion = ahora().replace(tzinfo=None) - dt_llegada
                    horas, rem = divmod(duracion.seconds, 3600)
                    minutos, _ = divmod(rem, 60)

                    col_info.markdown(f"**{profesional}** esta en el domicilio de **{data['paciente']}**")
                    col_info.caption(
                        f"Ingreso a las {dt_llegada.strftime('%H:%M')} | Tiempo transcurrido: {horas}h {minutos}m"
                    )

                    if col_btn.button("Forzar salida", key=f"force_out_{profesional}", width='stretch'):
                        st.session_state.setdefault("checkin_db", [])
                        st.session_state["checkin_db"].append(
                            {
                                "paciente": data["paciente"],
                                "profesional": profesional,
                                "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "tipo": f"SALIDA (Forzada por Admin: {user.get('nombre', 'Admin')})",
                                "empresa": mi_empresa,
                            }
                        )
                        guardar_datos(spinner=True)
                        queue_toast(f"Salida forzada registrada correctamente para {profesional}.")
                        st.rerun()
    else:
        st.success("En este momento no hay profesionales con guardias abiertas en domicilios.")

    st.divider()
    st.markdown("#### Auditoria de movimientos del dia")
    if chks_hoy:
        import pandas as pd
        df_chks = pd.DataFrame(chks_hoy).drop(columns=["empresa"], errors="ignore")
        df_chks = df_chks.rename(
            columns={
                "paciente": "Paciente",
                "profesional": "Profesional",
                "fecha_hora": "Fecha y Hora",
                "tipo": "Accion",
            }
        )
        limite = seleccionar_limite_registros(
            "Movimientos a mostrar",
            len(df_chks),
            key=f"limite_asistencia_{mi_empresa}",
            default=30,
        )
        df_mov = df_chks.tail(limite).iloc[::-1]
        with lista_plegable("Movimientos del día", count=len(df_mov), expanded=False, height=460):
            mostrar_dataframe_con_scroll(df_mov, height=400)
    else:
        st.warning(
            "No hay fichadas registradas hoy para esta clinica. Los movimientos aparecen cuando el equipo usa **Fichar LLEGADA/SALIDA** en Visitas con GPS o registro equivalente."
        )

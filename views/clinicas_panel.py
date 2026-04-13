"""Panel global SuperAdmin: clinicas registradas, suspension logica y reactivacion."""

import io

import pandas as pd
import streamlit as st

from core.clinicas_control import (
    contar_usuarios_por_clinica,
    norm_empresa_key,
    reactivar_clinica,
    sincronizar_clinicas_desde_datos,
    suspender_clinica,
)
from core.database import guardar_datos
from core.utils import ahora, registrar_auditoria_legal
from core.view_helpers import bloque_estado_vacio


def _registrar_cambio_clinica(user, accion: str, nombre_clinica: str, key_norm: str, detalle: str = "") -> None:
    actor = str(user.get("nombre", "") or "SuperAdmin").strip() or "SuperAdmin"
    mat = str(user.get("matricula", "") or "").strip()
    registrar_auditoria_legal(
        "Clinicas (panel global)",
        "GLOBAL",
        accion,
        actor,
        matricula=mat,
        detalle=detalle[:2000] if detalle else "",
        referencia=key_norm,
        empresa=nombre_clinica,
    )
    st.session_state.setdefault("logs_db", [])
    st.session_state["logs_db"].append(
        {
            "F": ahora().strftime("%d/%m/%Y"),
            "H": ahora().strftime("%H:%M"),
            "U": actor,
            "E": nombre_clinica,
            "A": f"Clinica: {accion}",
        }
    )


def _historial_eventos_clinicas(session_state, limite: int = 30):
    aud = session_state.get("auditoria_legal_db") or []
    filas = []
    for item in reversed(aud):
        if not isinstance(item, dict):
            continue
        if str(item.get("tipo_evento", "")).strip() != "Clinicas (panel global)":
            continue
        filas.append(
            {
                "Fecha": item.get("fecha", ""),
                "Accion": item.get("accion", ""),
                "Clinica": item.get("empresa", ""),
                "Actor": item.get("actor", ""),
                "Detalle": (item.get("detalle", "") or "")[:120],
            }
        )
        if len(filas) >= limite:
            break
    return filas


def _listado_usuarios_clinica(session_state, key_norm: str):
    filas = []
    for login, u in (session_state.get("usuarios_db") or {}).items():
        if not isinstance(u, dict):
            continue
        if str(login).strip().lower() == "admin":
            continue
        emp = str(u.get("empresa", "") or "").strip()
        if norm_empresa_key(emp) != key_norm:
            continue
        rol = str(u.get("rol", "") or "").strip()
        if rol in {"SuperAdmin", "Admin"}:
            continue
        filas.append(
            {
                "Login": str(login),
                "Nombre": str(u.get("nombre", "") or ""),
                "Rol": rol,
                "Estado usuario": str(u.get("estado", "Activo") or "Activo"),
            }
        )
    return sorted(filas, key=lambda x: (x["Rol"], x["Login"].lower()))


def render_clinicas_panel(mi_empresa, user, rol):
    user = user or {}
    rol_n = str(rol or user.get("rol", "") or "").strip().lower()
    if rol_n not in {"superadmin", "admin"}:
        st.error("Solo el perfil SuperAdmin puede acceder al panel global de clinicas.")
        return

    sincronizar_clinicas_desde_datos(st.session_state)

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Clinicas — panel global</h2>
            <p class="mc-hero-text">Listado unificado de clinicas, usuarios vinculados y estado operativo. La suspension es logica: corta el login del equipo de esa empresa hasta la reactivacion; no borra datos.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Cobranzas / abono</span>
                <span class="mc-chip">Suspension logica</span>
                <span class="mc-chip">SuperAdmin</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "Los usuarios **SuperAdmin** no quedan bloqueados por la suspension de una clinica. "
        "El login de emergencia **admin** sigue disponible para operacion interna MediCare."
    )
    st.success(
        "Flujo tipico: revisar **Estado** y cantidad de usuarios · usar **Suspender** solo con motivo claro (abono / decision administrativa) · "
        "**Reactivar** cuando corresponda · exportar CSV si necesitas auditoria externa. El historial de eventos queda en **Auditoria legal**."
    )

    conteos = contar_usuarios_por_clinica(st.session_state)
    db = st.session_state.get("clinicas_db") or {}
    if not isinstance(db, dict):
        st.session_state["clinicas_db"] = {}
        db = st.session_state["clinicas_db"]

    filas_resumen = []
    for key_norm, reg in sorted(db.items(), key=lambda x: str(x[1].get("nombre_display", x[0])).lower()):
        if not isinstance(reg, dict):
            continue
        nombre = str(reg.get("nombre_display") or key_norm).strip() or key_norm
        estado = str(reg.get("estado", "Activa") or "Activa")
        c = conteos.get(key_norm, {"total": 0, "coordinadores": 0, "operativos": 0, "administrativos": 0})
        filas_resumen.append(
            {
                "Clinica": nombre,
                "Estado": estado,
                "Usuarios": c["total"],
                "Coordinadores": c["coordinadores"],
                "Operativos / clinica": c["operativos"],
                "Administrativos": c["administrativos"],
                "Motivo baja": reg.get("motivo_baja", "") or "",
                "Actualizado": reg.get("actualizado_en", "") or "",
                "_key": key_norm,
            }
        )

    if not filas_resumen:
        bloque_estado_vacio(
            "Sin clínicas en el panel",
            "Todavía no hay clínicas registradas en el resumen global.",
            sugerencia="Aparecen al dar de alta usuarios o pacientes con empresa asignada, o al sincronizar datos.",
        )
        return

    df = pd.DataFrame(filas_resumen)
    n_total = len(filas_resumen)
    n_susp = sum(1 for r in filas_resumen if str(r["Estado"]).strip().lower() == "suspendida")
    n_act = n_total - n_susp
    m1, m2, m3 = st.columns(3)
    m1.metric("Clinicas registradas", n_total)
    m2.metric("Activas", n_act)
    m3.metric("Suspendidas", n_susp)

    st.markdown("##### Resumen")
    df_pub = df.drop(columns=["_key"], errors="ignore")
    st.dataframe(
        df_pub,
        use_container_width=True,
        hide_index=True,
        height=min(420, 60 + len(df) * 38),
    )
    buf = io.BytesIO()
    df_pub.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(
        "Descargar CSV — estado de clinicas",
        data=buf.getvalue(),
        file_name=f"clinicas_medicare_{ahora().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="clinicas_dl_csv_resumen",
        help="Exporta la tabla de resumen para control interno o facturacion.",
    )

    st.markdown("##### Gestion por clinica")
    opciones = [f"{r['Clinica']} ({r['Estado']})" for r in filas_resumen]
    idx_map = {lbl: i for i, lbl in enumerate(opciones)}
    elegido = st.selectbox("Seleccionar clinica", opciones, key="clinicas_panel_sel")
    i = idx_map[elegido]
    row = filas_resumen[i]
    key_norm = row["_key"]
    reg = db.get(key_norm, {})

    c1, c2, c3 = st.columns(3)
    c1.metric("Estado actual", row["Estado"])
    c2.metric("Usuarios afectados al suspender", row["Usuarios"])
    c3.metric("Coordinadores", row["Coordinadores"])

    with st.expander("Personal vinculado a esta clinica", expanded=False):
        usuarios = _listado_usuarios_clinica(st.session_state, key_norm)
        if not usuarios:
            st.caption("Sin usuarios operativos listados (solo SuperAdmin u otras excepciones).")
        else:
            st.dataframe(pd.DataFrame(usuarios), use_container_width=True, hide_index=True, height=min(320, 60 + len(usuarios) * 36))

    st.markdown("##### Suspender o reactivar (baja / alta logica)")
    motivo = st.text_input(
        "Motivo de suspension (opcional, queda registrado)",
        value=str(reg.get("motivo_baja", "") or ""),
        key=f"clin_motivo_{key_norm}",
        placeholder="Ej: mora facturacion marzo, solicitud de la clinica, etc.",
    )

    b1, b2 = st.columns(2)
    with b1:
        if st.button(
            "Suspender clinica (bloquea accesos)",
            type="primary",
            use_container_width=True,
            key=f"clin_susp_{key_norm}",
            disabled=str(row["Estado"]).strip().lower() == "suspendida",
        ):
            suspender_clinica(st.session_state, key_norm, motivo)
            usuarios_afectados = row["Usuarios"]
            detalle = (
                f"Suspension logica. Usuarios operativos afectados (aprox.): {usuarios_afectados}. "
                f"Motivo: {motivo.strip() or 'Sin motivo consignado'}."
            )
            _registrar_cambio_clinica(user, "Suspension de clinica", nombre, key_norm, detalle)
            guardar_datos()
            st.success(f"Clinica suspendida: {nombre}. Los usuarios de esa empresa no podran iniciar sesion.")
            st.rerun()
    with b2:
        if st.button(
            "Reactivar clinica",
            type="secondary",
            use_container_width=True,
            key=f"clin_react_{key_norm}",
            disabled=str(row["Estado"]).strip().lower() != "suspendida",
        ):
            reactivar_clinica(st.session_state, key_norm)
            _registrar_cambio_clinica(
                user,
                "Reactivacion de clinica",
                nombre,
                key_norm,
                "Servicio habilitado nuevamente. Accesos restaurados para coordinadores, operativos y administrativos.",
            )
            guardar_datos()
            st.success(f"Clinica reactivada: {nombre}.")
            st.rerun()

    with st.expander("Historial de suspensiones y reactivaciones (auditoria)", expanded=False):
        hist = _historial_eventos_clinicas(st.session_state, limite=40)
        if not hist:
            st.caption("Todavia no hay eventos registrados en auditoria para este panel.")
        else:
            df_hist = pd.DataFrame(hist)
            st.dataframe(df_hist, use_container_width=True, hide_index=True, height=min(380, 60 + len(hist) * 36))
            hbuf = io.BytesIO()
            df_hist.to_csv(hbuf, index=False, encoding="utf-8-sig")
            st.download_button(
                "Descargar CSV — historial auditoria clinicas",
                data=hbuf.getvalue(),
                file_name=f"auditoria_clinicas_{ahora().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="clinicas_dl_csv_hist",
            )
            st.caption("Las entradas provienen de `auditoria_legal_db` con tipo **Clinicas (panel global)**.")

    st.caption(f"Ultima actualizacion de ficha: {reg.get('actualizado_en') or '—'} | Hora servidor: {ahora().strftime('%d/%m/%Y %H:%M')}")

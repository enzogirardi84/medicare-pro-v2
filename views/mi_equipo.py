from typing import Dict, Any

import streamlit as st

from core.database import guardar_datos
from core.utils import (
    filtrar_registros_empresa,
    puede_accion,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)

# --- Constantes ---
TITULOS_PROFESIONALES = [
    "Médico/a",
    "Lic. en Enfermería",
    "Enfermero/a",
    "Kinesiólogo/a",
    "Fonoaudiólogo/a",
    "Nutricionista",
    "Psicólogo/a",
    "Acompañante Terapéutico",
    "Trabajador/a Social",
    "Administrativo/a",
    "Otro",
]

ROLES_SISTEMA_SUPERADMIN = ["Operativo", "Administrativo", "Medico", "Enfermeria", "Auditoria", "Coordinador", "SuperAdmin"]
ROLES_SISTEMA_NORMAL = ["Operativo", "Administrativo", "Medico", "Enfermeria", "Auditoria", "Coordinador"]


def _render_alta_usuario(mi_empresa: str, rol_actual: str, user: Dict[str, Any]) -> None:
    """Renderiza el formulario estructurado para dar de alta un nuevo profesional/usuario."""
    with st.form("equipo_alta_form", clear_on_submit=True):
        st.markdown("##### 1. Datos Personales y Profesionales")
        u_nm = st.text_input("Nombre Completo del Profesional *", placeholder="Ej: Dra. María López")
        
        col_dni, col_mt, col_ti = st.columns(3)
        u_dni = col_dni.text_input("DNI *", placeholder="Sin puntos")
        u_mt = col_mt.text_input("Matrícula Profesional", placeholder="M.P 12345")
        u_ti = col_ti.selectbox("Título / Cargo", TITULOS_PROFESIONALES)

        st.markdown("##### 2. Credenciales de Acceso")
        col_id, col_pw, col_pin = st.columns([2, 2, 1])
        u_id = col_id.text_input("Usuario (Login) *", placeholder="ej: maria.lopez")
        u_pw = col_pw.text_input("Clave de acceso *", type="password", placeholder="••••••••")
        u_pin = col_pin.text_input("PIN (4 dígitos) *", max_chars=4, placeholder="1234", help="Se usa para firmar evoluciones y recetas de forma rápida.")

        st.markdown("##### 3. Asignación en el Sistema")
        col_emp, col_rl = st.columns(2)
        if rol_actual == "SuperAdmin":
            u_emp = col_emp.text_input("Asignar a Clínica / Empresa", value=mi_empresa)
            opciones_roles = ROLES_SISTEMA_SUPERADMIN
        else:
            u_emp = mi_empresa
            col_emp.info(f"Empresa fijada: {mi_empresa}")
            opciones_roles = ROLES_SISTEMA_NORMAL
            
        u_rl = col_rl.selectbox("Rol de permisos en el sistema", opciones_roles)

        if st.form_submit_button("Habilitar Acceso al Profesional", use_container_width=True, type="primary"):
            # Validaciones de seguridad
            if not u_id or not u_pw or not u_pin or not u_dni or not u_nm:
                st.error("Todos los campos marcados con (*) son obligatorios.")
                return
            if len(u_pin) != 4 or not u_pin.isdigit():
                st.error("El PIN de firma debe tener exactamente 4 dígitos numéricos.")
                return
                
            login_limpio = u_id.strip().lower()
            if login_limpio in st.session_state["usuarios_db"]:
                st.error(f"El usuario de login '{login_limpio}' ya existe. Elija otro.")
                return

            # Guardado en base de datos
            empresa_final = u_emp.strip() if isinstance(u_emp, str) else mi_empresa
            st.session_state["usuarios_db"][login_limpio] = {
                "pass": u_pw.strip(),
                "nombre": u_nm.strip(),
                "rol": u_rl,
                "titulo": u_ti,
                "empresa": empresa_final,
                "matricula": u_mt.strip(),
                "dni": u_dni.strip(),
                "estado": "Activo",
                "pin": u_pin.strip(),
            }
            
            registrar_auditoria_legal(
                "Equipo", "GLOBAL", "Alta de usuario",
                user.get("nombre", "Sistema"), user.get("matricula", ""),
                f"Se creó el usuario {login_limpio} con rol {u_rl} para {empresa_final}.",
                referencia=login_limpio,
            )
            guardar_datos()
            st.toast(f"Usuario {login_limpio} habilitado correctamente.", icon="✅")
            st.rerun()


def _cambiar_estado_usuario(login: str, nuevo_estado: str, user: Dict[str, Any]) -> None:
    """Lógica encapsulada para suspender o reactivar a un miembro del equipo."""
    st.session_state["usuarios_db"][login]["estado"] = nuevo_estado
    accion_auditoria = "Suspensión de usuario" if nuevo_estado == "Bloqueado" else "Reactivación de usuario"
    
    registrar_auditoria_legal(
        "Equipo", "GLOBAL", accion_auditoria,
        user.get("nombre", "Sistema"), user.get("matricula", ""),
        f"Se cambió el estado del usuario {login} a {nuevo_estado}.",
        referencia=login,
    )
    guardar_datos()
    st.toast(f"Estado de {login} actualizado a {nuevo_estado}.", icon="🔄")
    st.rerun()


def _render_padron_equipo(mi_empresa: str, rol_actual: str, user: Dict[str, Any], puede_cambiar_est: bool, puede_elim: bool) -> None:
    """Renderiza el padrón de usuarios con buscador, scroll anti-colapso y visualización de PIN."""
    st.markdown("##### Buscador y Padrón Activo")
    buscar_usuario = st.text_input("🔍 Buscar usuario por nombre, login, DNI o rol...", "").lower()

    # Preparar y filtrar lista de usuarios
    usuarios_base = [{"_login": login, **datos} for login, datos in st.session_state["usuarios_db"].items()]
    
    usuarios_filtrados = {
        fila["_login"]: {k: v for k, v in fila.items() if k != "_login"}
        for fila in filtrar_registros_empresa(usuarios_base, mi_empresa, rol_actual)
        if (
            not buscar_usuario
            or buscar_usuario in fila["_login"].lower()
            or buscar_usuario in str(fila.get("nombre", "")).lower()
            or buscar_usuario in str(fila.get("dni", "")).lower()
            or buscar_usuario in str(fila.get("rol", "")).lower()
        )
    }

    if not usuarios_filtrados:
        st.info("No se encontraron profesionales con ese criterio de búsqueda.")
        return

    # Quitar al usuario "admin" del sistema por seguridad de visualización (opcional, basado en tu código previo)
    usuarios_ordenados = [(u, d) for u, d in usuarios_filtrados.items() if u != "admin"]
    
    st.caption(f"Mostrando {len(usuarios_ordenados)} miembros del equipo.")
    
    limite = seleccionar_limite_registros(
        "Usuarios a mostrar", len(usuarios_ordenados),
        key="equipo_limite_usuarios", default=20, opciones=(10, 20, 50, 100)
    )

    # Contenedor Anti-Colapso
    with st.container(height=600):
        for login_usr, datos_usr in usuarios_ordenados[:limite]:
            with st.container(border=True):
                col_info, col_acciones = st.columns([3, 1.5])
                
                estado_actual = datos_usr.get("estado", "Activo")
                es_activo = estado_actual == "Activo"
                badge = "🟢 Activo" if es_activo else "🔴 Bloqueado"

                # --- Columna Izquierda: Información Detallada ---
                with col_info:
                    st.markdown(f"**{badge} | {datos_usr.get('nombre', 'Sin nombre')}** ({datos_usr.get('titulo', 'S/D')})")
                    
                    # Fila de badges visuales con el PIN destacado
                    st.markdown(
                        f"""
                        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;">
                            <span class="mc-chip">Login: <b>{login_usr}</b></span>
                            <span class="mc-chip" style="background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B;">
                                🔑 PIN: <b>{datos_usr.get('pin', 'S/D')}</b>
                            </span>
                            <span class="mc-chip">Rol: {datos_usr.get('rol', 'S/D')}</span>
                            <span class="mc-chip">DNI: {datos_usr.get('dni', 'S/D')}</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    if datos_usr.get('matricula'):
                        st.caption(f"Matrícula: {datos_usr.get('matricula')} | Empresa: {datos_usr.get('empresa', 'S/D')}")
                    else:
                        st.caption(f"Empresa asignada: {datos_usr.get('empresa', 'S/D')}")

                # --- Columna Derecha: Acciones ---
                with col_acciones:
                    if puede_cambiar_est:
                        if es_activo:
                            if st.button("⏸️ Suspender", key=f"susp_{login_usr}", use_container_width=True):
                                _cambiar_estado_usuario(login_usr, "Bloqueado", user)
                        else:
                            if st.button("▶️ Reactivar", key=f"reac_{login_usr}", use_container_width=True, type="primary"):
                                _cambiar_estado_usuario(login_usr, "Activo", user)
                    
                    if puede_elim:
                        chk_del = st.checkbox("Confirmar baja", key=f"chk_del_{login_usr}")
                        if st.button("🗑️ Eliminar", key=f"del_{login_usr}", use_container_width=True, disabled=not chk_del):
                            registrar_auditoria_legal(
                                "Equipo", "GLOBAL", "Eliminación de usuario",
                                user.get("nombre", "Sistema"), user.get("matricula", ""),
                                f"Se eliminó permanentemente el usuario {login_usr}.", referencia=login_usr,
                            )
                            del st.session_state["usuarios_db"][login_usr]
                            guardar_datos()
                            st.toast(f"Usuario {login_usr} eliminado permanentemente.", icon="🗑️")
                            st.rerun()
                    elif not puede_cambiar_est:
                        st.caption("Sin permisos de gestión.")


# --- Función Principal (Enrutador) ---
def render_mi_equipo(mi_empresa: str, rol: str, user: Dict[str, Any] = None) -> None:
    user = user or {}
    
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Gestión de Personal e Identidades</h2>
            <p class="mc-hero-text">Administra los accesos, roles y credenciales (PIN) de los profesionales asignados a <b>{mi_empresa}</b>. Las suspensiones bloquean el acceso inmediatamente.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    puede_crear = puede_accion(rol, "equipo_crear_usuario")
    puede_cambiar_estado = puede_accion(rol, "equipo_cambiar_estado")
    puede_eliminar = puede_accion(rol, "equipo_eliminar_usuario")

    tab_alta, tab_padron = st.tabs(["➕ Alta de Profesional", "📋 Padrón y Control de Accesos"])

    with tab_alta:
        if puede_crear:
            _render_alta_usuario(mi_empresa, rol, user)
        else:
            st.warning("La gestión de altas de usuarios queda reservada a Coordinación y Administración.")

    with tab_padron:
        _render_padron_equipo(mi_empresa, rol, user, puede_cambiar_estado, puede_eliminar)

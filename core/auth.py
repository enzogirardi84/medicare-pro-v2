import streamlit as st

from core.database import cargar_datos, guardar_datos
from core.utils import DEFAULT_ADMIN_USER, ahora, asegurar_usuarios_base


def render_login():
    if "logeado" not in st.session_state:
        st.session_state["logeado"] = False

    if not st.session_state["logeado"]:
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.markdown("<br><h2 style='text-align:center; color:#3b82f6;'>MediCare Enterprise PRO V9.12</h2>", unsafe_allow_html=True)
            modo_auth = st.radio(
                "Acceso",
                ["Iniciar sesion", "Olvide mi contrasena"],
                horizontal=True,
                label_visibility="collapsed",
            )

            if modo_auth == "Iniciar sesion":
                with st.form("login", clear_on_submit=True):
                    u = st.text_input("Usuario")
                    p = st.text_input("Contrasena", type="password")
                    if st.form_submit_button("Ingresar al Sistema", width="stretch"):
                        db_f = cargar_datos(force=True)
                        if db_f:
                            for k, v in db_f.items():
                                st.session_state[k] = v
                        asegurar_usuarios_base()
                        u_limpio = u.strip().lower()
                        usuario_encontrado = None
                        for key_db in st.session_state["usuarios_db"].keys():
                            if key_db.strip().lower() == u_limpio:
                                usuario_encontrado = key_db
                                break

                        if usuario_encontrado:
                            user_data = st.session_state["usuarios_db"][usuario_encontrado]
                            if user_data.get("estado", "Activo") == "Bloqueado":
                                st.error("Acceso suspendido.")
                            elif str(user_data["pass"]).strip() == p.strip():
                                st.session_state["u_actual"] = user_data
                                st.session_state["logeado"] = True
                                st.session_state["logs_db"].append(
                                    {
                                        "F": ahora().strftime("%d/%m/%Y"),
                                        "H": ahora().strftime("%H:%M"),
                                        "U": user_data["nombre"],
                                        "E": user_data["empresa"],
                                        "A": "Login",
                                    }
                                )
                                guardar_datos()
                                st.rerun()
                            else:
                                if u_limpio == "admin" and p.strip() == str(DEFAULT_ADMIN_USER["pass"]).strip():
                                    user_data = DEFAULT_ADMIN_USER.copy()
                                    st.session_state["usuarios_db"]["admin"] = user_data
                                    st.session_state["u_actual"] = user_data
                                    st.session_state["logeado"] = True
                                    st.session_state["logs_db"].append(
                                        {
                                            "F": ahora().strftime("%d/%m/%Y"),
                                            "H": ahora().strftime("%H:%M"),
                                            "U": user_data["nombre"],
                                            "E": user_data["empresa"],
                                            "A": "Login emergencia admin",
                                        }
                                    )
                                    guardar_datos()
                                    st.rerun()
                                else:
                                    st.error("Acceso denegado.")
                        else:
                            if u_limpio == "admin" and p.strip() == str(DEFAULT_ADMIN_USER["pass"]).strip():
                                user_data = DEFAULT_ADMIN_USER.copy()
                                st.session_state["usuarios_db"]["admin"] = user_data
                                st.session_state["u_actual"] = user_data
                                st.session_state["logeado"] = True
                                st.session_state["logs_db"].append(
                                    {
                                        "F": ahora().strftime("%d/%m/%Y"),
                                        "H": ahora().strftime("%H:%M"),
                                        "U": user_data["nombre"],
                                        "E": user_data["empresa"],
                                        "A": "Login emergencia admin",
                                    }
                                )
                                guardar_datos()
                                st.rerun()
                            else:
                                st.error("Acceso denegado.")
            else:
                with st.form("recover", clear_on_submit=True):
                    st.info("Para crear una nueva contrasena, ingresa tu PIN de 4 digitos.")
                    rec_u = st.text_input("Usuario (Login)")
                    rec_emp = st.text_input("Empresa / Clinica asignada")
                    rec_pin = st.text_input("PIN de Seguridad", type="password", max_chars=4)
                    rec_pass = st.text_input("Nueva Contrasena", type="password")
                    if st.form_submit_button("Cambiar Contrasena", width="stretch"):
                        db_f = cargar_datos(force=True)
                        if db_f:
                            for k, v in db_f.items():
                                st.session_state[k] = v
                        asegurar_usuarios_base()
                        u_limpio = rec_u.strip().lower()
                        if u_limpio in st.session_state["usuarios_db"]:
                            user_data = st.session_state["usuarios_db"][u_limpio]
                            if user_data["empresa"].strip().lower() == rec_emp.strip().lower():
                                if str(user_data.get("pin", "")) == str(rec_pin).strip() and str(rec_pin).strip() != "":
                                    if len(rec_pass) >= 4:
                                        st.session_state["usuarios_db"][u_limpio]["pass"] = rec_pass
                                        guardar_datos()
                                        st.success("Contrasena actualizada.")
                                    else:
                                        st.error("Contrasena minima de 4 caracteres.")
                                else:
                                    st.error("PIN incorrecto.")
                            else:
                                st.error("Empresa incorrecta.")
                        else:
                            st.error("Usuario no existe.")
        st.stop()


def check_inactividad():
    if st.session_state.get("logeado"):
        if "ultima_actividad" not in st.session_state:
            st.session_state["ultima_actividad"] = ahora()
        else:
            minutos_inactivos = (ahora() - st.session_state["ultima_actividad"]).total_seconds() / 60.0
            if minutos_inactivos > 5.0:
                st.session_state["logeado"] = False
                st.session_state.pop("ultima_actividad", None)
                st.session_state.pop("u_actual", None)
                st.warning("Tu sesion se cerro automaticamente por inactividad (5 minutos).")
                st.rerun()
            else:
                st.session_state["ultima_actividad"] = ahora()

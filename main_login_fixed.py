"""
Sistema de Login con Transición Fluida - Medicare Pro

SOLUCIÓN AL PROBLEMA DE PARPADEO:
- Placeholder persistente que nunca se destruye
- Estado de transición intermedio ("authenticating")
- CSS overlay para transición suave
- Batch state updates para evitar reruns múltiples
"""

import streamlit as st
import time
from datetime import datetime

# ============================================================
# CONFIGURACIÓN DE PÁGINA (Debe ser lo primero)
# ============================================================
st.set_page_config(
    page_title="Medicare Pro - Sistema de Gestión Clínica",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS PARA TRANSICIONES SUAVES (Evita el flash negro)
# ============================================================
st.markdown("""
<style>
    /* Ocultar el spinner por defecto de Streamlit para controlarlo manualmente */
    .stSpinner > div {
        border-top-color: #14b8a6 !important;
    }
    
    /* Transición suave para contenedores */
    .fade-in {
        animation: fadeIn 0.5s ease-in-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Overlay de transición que cubre la pantalla durante el cambio */
    .transition-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.5s ease-out;
    }
    
    .transition-overlay.hidden {
        opacity: 0;
        pointer-events: none;
    }
    
    /* Spinner personalizado */
    .custom-spinner {
        width: 60px;
        height: 60px;
        border: 4px solid rgba(20, 184, 166, 0.3);
        border-top: 4px solid #14b8a6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Skeleton loading para el dashboard */
    .skeleton {
        background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        height: 20px;
        margin: 10px 0;
    }
    
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    /* Contenedor principal siempre visible */
    .main-container {
        min-height: 100vh;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# INICIALIZACIÓN DE ESTADOS (Todos al inicio)
# ============================================================
def init_session_state():
    """Inicializa todos los estados necesarios."""
    defaults = {
        'usuario_autenticado': False,
        'authenticating': False,  # NUEVO: Estado intermedio de transición
        'auth_error': None,
        'usuario_actual': None,
        'login_timestamp': None,
        'transition_complete': False,  # Control de transición CSS
        '_placeholder_initialized': False  # Flag para evitar recreación
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================
# PLACEHOLDER PERSISTENTE (El secreto anti-parpadeo)
# ============================================================
# Este placeholder se crea UNA SOLA VEZ y nunca se destruye
if not st.session_state._placeholder_initialized:
    st.session_state._main_placeholder = st.empty()
    st.session_state._placeholder_initialized = True
    # Nunca recrear el placeholder - reutilizar siempre el mismo

main_placeholder = st.session_state._main_placeholder

# ============================================================
# OVERLAY DE TRANSICIÓN (Opcional, para efecto premium)
# ============================================================
def show_transition_overlay():
    """Muestra overlay durante la transición."""
    if st.session_state.authenticating and not st.session_state.transition_complete:
        st.markdown("""
        <div class="transition-overlay">
            <div style="text-align: center;">
                <div class="custom-spinner"></div>
                <p style="color: white; margin-top: 20px; font-family: sans-serif;">
                    Iniciando sesión...
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# CALLBACK OPTIMIZADO (Batch state updates)
# ============================================================
def verificar_credenciales():
    """
    Callback de login con transición suave.
    
    CRÍTICO: No usar st.rerun() aquí. Dejar que Streamlit maneje 
    el rerun automáticamente después del callback.
    """
    usuario = st.session_state.get("input_usuario", "").strip()
    password = st.session_state.get("input_password", "").strip()
    
    # Validación básica
    if not usuario or not password:
        st.session_state.auth_error = "Ingrese usuario y contraseña"
        return
    
    # INICIO DE TRANSICIÓN: Cambiar a estado intermedio PRIMERO
    # Esto evita el flash negro manteniendo el formulario visible
    st.session_state.authenticating = True
    st.session_state.auth_error = None
    
    # Validacion contra base de datos real
    from core.database import supabase
    from core.password_crypto import verificar_password

    if not supabase:
        st.session_state.auth_error = "Servicio no disponible"
        st.session_state.authenticating = False
        return

    try:
        response = (
            supabase.table("usuarios")
            .select("login, pass_hash, rol, empresa, nombre, estado")
            .eq("login", usuario.lower().strip())
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            user_row = response.data[0]
            if user_row.get("estado") == "Bloqueado":
                st.session_state.auth_error = "Usuario bloqueado"
                st.session_state.authenticating = False
                return
            if verificar_password(password, user_row.get("pass_hash", "")):
                st.session_state.usuario_autenticado = True
                st.session_state.usuario_actual = {
                    "usuario": usuario,
                    "nombre": user_row.get("nombre", usuario),
                    "rol": user_row.get("rol", "operativo"),
                    "login_time": datetime.now().isoformat()
                }
                st.session_state.login_timestamp = datetime.now()
                st.session_state.input_usuario = ""
                st.session_state.input_password = ""
                st.session_state.transition_complete = True
                return
    except Exception:
        pass

    st.session_state.authenticating = False
    st.session_state.auth_error = "Credenciales incorrectas"
    st.session_state.usuario_autenticado = False

# ============================================================
# VISTA DE LOGIN CON ESTADO DE TRANSICIÓN
# ============================================================
def render_login_view():
    """Renderiza el formulario de login."""
    
    with main_placeholder.container():
        # CSS container para animación
        st.markdown('<div class="main-container fade-in">', unsafe_allow_html=True)
        
        # Centrado visual
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # Logo y título
            st.markdown("""
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #14b8a6; margin-bottom: 10px;">🏥 Medicare Pro</h1>
                <p style="color: #94a3b8;">Sistema de Gestión Clínica</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Card de login con estilo glassmorphism
            with st.container():
                st.markdown("""
                <div style="
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    padding: 30px;
                    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
                ">
                """, unsafe_allow_html=True)
                
                st.subheader("🔐 Acceso al Sistema")
                
                # Mostrar error si existe
                if st.session_state.auth_error:
                    st.error(f"⚠️ {st.session_state.auth_error}")
                
                # Formulario
                usuario = st.text_input(
                    "Usuario / DNI",
                    key="input_usuario",
                    placeholder="Ingrese su usuario",
                    disabled=st.session_state.authenticating  # Deshabilitar durante transición
                )
                
                password = st.text_input(
                    "Contraseña",
                    type="password",
                    key="input_password",
                    placeholder="Ingrese su contraseña",
                    disabled=st.session_state.authenticating
                )
                
                # Botón de login
                login_disabled = st.session_state.authenticating or not usuario or not password
                
                if st.button(
                    "Ingresar",
                    type="primary",
                    width='stretch',
                    disabled=login_disabled,
                    on_click=verificar_credenciales
                ):
                    pass  # El callback maneja todo
                
                # Spinner de validación (solo visible durante authenticating)
                if st.session_state.authenticating:
                    with st.spinner("🔄 Validando credenciales..."):
                        # Pequeño delay para permitir que el spinner se muestre
                        # En producción, quitar esto o mantenerlo muy corto
                        time.sleep(0.5)
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Footer
                st.markdown("""
                <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">
                    <p>¿Olvidó su contraseña? Contacte al administrador</p>
                    <p>© 2026 Medicare Pro - v2.0.0</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# SKELETON SCREEN (Para carga del dashboard)
# ============================================================
def render_skeleton_dashboard():
    """Renderiza esqueleto del dashboard mientras carga."""
    with main_placeholder.container():
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        
        # Header skeleton
        st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <div class="skeleton" style="width: 300px; height: 40px;"></div>
            <div class="skeleton" style="width: 150px; height: 40px;"></div>
        </div>
        """, unsafe_allow_html=True)
        
        # KPIs skeleton
        cols = st.columns(4)
        for col in cols:
            with col:
                st.markdown('<div class="skeleton" style="height: 100px;"></div>', unsafe_allow_html=True)
        
        # Content skeleton
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown('<div class="skeleton" style="height: 400px;"></div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="skeleton" style="height: 200px;"></div>', unsafe_allow_html=True)
            st.markdown('<div class="skeleton" style="height: 180px;"></div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# VISTA DEL DASHBOARD
# ============================================================
def render_dashboard():
    """Renderiza el dashboard principal."""
    
    with main_placeholder.container():
        st.markdown('<div class="main-container fade-in">', unsafe_allow_html=True)
        
        # Header
        col1, col2, col3 = st.columns([2, 4, 2])
        
        with col1:
            st.title("🏥 Medicare Pro")
        
        with col2:
            usuario = st.session_state.usuario_actual
            st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="margin: 0; color: #14b8a6;">👤 {usuario['nombre']}</p>
                <p style="margin: 0; font-size: 12px; color: #64748b;">{usuario['rol'].upper()}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if st.button("🚪 Cerrar Sesión", type="secondary", width='stretch'):
                # Limpiar todos los estados de auth
                st.session_state.usuario_autenticado = False
                st.session_state.authenticating = False
                st.session_state.usuario_actual = None
                st.session_state.auth_error = None
                st.session_state.transition_complete = False
                st.rerun()
        
        st.divider()
        
        # Contenido del dashboard
        st.success("✅ ¡Bienvenido! Inicio de sesión fluido sin parpadeos.")
        
        # Aquí iría tu dashboard real...
        st.markdown("### 📊 Panel de Control")
        
        # Tabs de ejemplo
        tab1, tab2, tab3 = st.tabs(["Pacientes", "Turnos", "Reportes"])
        
        with tab1:
            st.info("🚧 Módulo de pacientes cargado")
            # Aquí llamarías a tu función de pacientes real
        
        with tab2:
            st.info("🚧 Módulo de turnos cargado")
        
        with tab3:
            st.info("🚧 Módulo de reportes cargado")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# CONTROLADOR PRINCIPAL CON MÁQUINA DE ESTADOS
# ============================================================
def main():
    """Controlador principal de la aplicación."""
    
    # Mostrar overlay durante transición si aplica
    show_transition_overlay()
    
    # MÁQUINA DE ESTADOS
    if not st.session_state.usuario_autenticado:
        # ESTADO 1: No autenticado (login)
        render_login_view()
        
        # Si está en transición, planificar cambio de vista
        if st.session_state.authenticating and st.session_state.transition_complete:
            # Pequeño delay para efecto visual, luego mostrar skeleton
            # En producción, quitar el sleep o mantenerlo mínimo
            time.sleep(0.3)
            st.rerun()  # Este rerun ahora va al else (dashboard)
    
    else:
        # ESTADO 2: Autenticado (dashboard)
        
        # Si venimos de una transición, primero mostrar skeleton
        if st.session_state.authenticating:
            render_skeleton_dashboard()
            
            # Simular carga de datos (reemplazar con tu carga real)
            time.sleep(0.5)
            
            # Marcar transición como finalizada
            st.session_state.authenticating = False
            st.rerun()  # Segundo rerun ahora muestra el dashboard real
        
        else:
            # ESTADO 3: Dashboard completamente cargado
            render_dashboard()

# Ejecutar
if __name__ == "__main__":
    main()

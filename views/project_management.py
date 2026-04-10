import pandas as pd
import streamlit as st

from core.utils import mostrar_dataframe_con_scroll


DOC_URL = "https://docs.google.com/document/d/1D8Gh4VWW_zHDbBw26c23PxxwR4ImjoMJAbYveINKhUI/edit?usp=sharing"

OWNERS = [
    {
        "titulo": "Producto y negocio",
        "nombre": "Enzo Girardi",
        "detalle": "Creador y propietario del producto. Define reglas de negocio, alcance clinico y prioridades.",
    },
    {
        "titulo": "Arquitectura tecnica",
        "nombre": "Dario Lanfranco",
        "detalle": "Socio tecnico y arquitecto. Lidera la migracion silenciosa y la nueva arquitectura escalable.",
    },
]

CURRENT_STACK = [
    "Python 3.x como lenguaje principal.",
    "Streamlit como frontend y backend reactivo en una SPA unica.",
    "Supabase como BaaS con PostgreSQL y REST API.",
    "Pandas para procesamiento, cruces y exportes.",
    "FPDF para historias clinicas, consentimientos y recibos.",
    "streamlit-geolocation y Nominatim para GPS y direccion real.",
    "streamlit-drawable-canvas y Pillow para firmas tactiles.",
    "Base64 para adjuntos, fotos y ordenes medicas dentro del JSON persistido.",
]

TARGET_ARCHITECTURE = [
    "Angular para la experiencia visual y la navegacion modular.",
    "NestJS sobre Node.js para seguridad, trafico y persistencia relacional.",
    "Supabase como base de datos comun durante la convivencia tecnologica.",
    "Python como motor de inteligencia clinica, analitica avanzada y servicios pesados.",
    "Arquitectura poliglota para escalar sin perder la logica clinica ya consolidada.",
]

MIGRATION_OBJECTIVES = [
    "Optimizar uso de recursos y consumo de datos en entornos moviles.",
    "Preparar la plataforma para cientos de usuarios concurrentes y multiples clinicas.",
    "Evitar caidas de servicio y perdida de datos durante el crecimiento.",
    "Separar el frente visual del motor operativo sin romper la operacion actual.",
]

MILESTONES = [
    {
        "Hito": "1. Cimientos y Cerebro",
        "Ventana": "Mes 1",
        "Foco": "Base tecnica",
        "Accion principal": "Configurar NestJS y Prisma conectados a Supabase con un esquema normalizado.",
        "Resultado esperado": "Tablas de pacientes, visitas, usuarios y medicamentos listas para escalar.",
    },
    {
        "Hito": "2. Puerta de Entrada y Seguridad",
        "Ventana": "Mes 2",
        "Foco": "Roles y login",
        "Accion principal": "Implementar autenticacion, permisos y perfiles por rol en backend.",
        "Resultado esperado": "Acceso real por perfil con visibilidad acorde a cada usuario.",
    },
    {
        "Hito": "3. Corazon Operativo",
        "Ventana": "Mes 3-4",
        "Foco": "Visitas y GPS",
        "Accion principal": "Migrar visitas, geolocalizacion y endpoints operativos al nuevo backend.",
        "Resultado esperado": "Las visitas ya funcionan sobre la nueva base sin romper el servicio.",
    },
    {
        "Hito": "4. Estetica y Lanzamiento",
        "Ventana": "Mes 5",
        "Foco": "Dashboard y UX",
        "Accion principal": "Construir el dashboard ejecutivo y la experiencia final en Angular.",
        "Resultado esperado": "Salida de MediCare PRO con tablero en tiempo real y experiencia enterprise.",
    },
]

ROLE_MATRIX = [
    {"Categoria": "Sistema", "Modulo": "Panel Global (Clinicas)", "SuperAdmin": "Si", "Coordinador": "No", "Operativo": "No", "Administrativo": "No"},
    {"Categoria": "Sistema", "Modulo": "Gestion de Equipo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "No"},
    {"Categoria": "Sistema", "Modulo": "Auditoria General", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "No"},
    {"Categoria": "Sistema", "Modulo": "Auditoria Legal", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "No"},
    {"Categoria": "Gestion", "Modulo": "Admision (Pacientes)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Parcial", "Administrativo": "Si"},
    {"Categoria": "Gestion", "Modulo": "Dashboard Ejecutivo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "Si"},
    {"Categoria": "Gestion", "Modulo": "Red de Profesionales", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "Si"},
    {"Categoria": "Gestion", "Modulo": "Telemedicina", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Visitas y Agenda", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "Si"},
    {"Categoria": "Clinica", "Modulo": "Historial (HC)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Signos Vitales", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Evolucion Medica", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Recetas / Medicacion", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Estudios / Ordenes", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Escalas Clinicas", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Pediatria (Curvas)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Balance Hidrico", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Clinica", "Modulo": "Emergencias", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "No"},
    {"Categoria": "Logistica", "Modulo": "Materiales (Gasto)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "Si"},
    {"Categoria": "Logistica", "Modulo": "Inventario / Stock", "SuperAdmin": "Si", "Coordinador": "No", "Operativo": "No", "Administrativo": "Si"},
    {"Categoria": "Contable", "Modulo": "Caja Diaria", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Solo hoy", "Administrativo": "Si"},
    {"Categoria": "Contable", "Modulo": "Cierre Diario", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "Si"},
    {"Categoria": "Contable", "Modulo": "Asistencia en Vivo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "Si"},
    {"Categoria": "Contable", "Modulo": "Control RRHH (GPS)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrativo": "Si"},
    {"Categoria": "Output", "Modulo": "Centro PDF", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrativo": "Si"},
]

WORK_METHOD = [
    "Sprints diarios con comunicacion por WhatsApp y Slack.",
    "Tablero simple en Jira o Trello con columnas Por hacer, En proceso, Para revisar y Listo.",
    "Definicion explicita de reglas de negocio y validaciones antes de cada migracion.",
]


def _render_listado(titulo, items):
    st.markdown(f"##### {titulo}")
    for item in items:
        st.markdown(f"- {item}")


def render_project_management(mi_empresa, user=None, rol=None):
    user = user or {}
    rol = rol or user.get("rol", "")

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Project Management MediCare Enterprise PRO</h2>
            <p class="mc-hero-text">Documento vivo de producto, arquitectura y roadmap de migracion para ordenar la evolucion de la plataforma sin frenar la operacion actual.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Stack actual</span>
                <span class="mc-chip">Migracion silenciosa</span>
                <span class="mc-chip">Roles y roadmap</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Empresa", mi_empresa or "MediCare")
    c2.metric("Estado", "Migracion silenciosa")
    c3.metric("Frontend destino", "Angular")
    c4.metric("Backend destino", "NestJS + Python")

    st.caption(
        f"Documento fuente integrado en la app. Ultima referencia cargada desde [Google Docs]({DOC_URL}). Rol actual: {rol or 'Sin rol'}."
    )

    col_owner_1, col_owner_2 = st.columns(2)
    for col, owner in zip((col_owner_1, col_owner_2), OWNERS):
        with col:
            with st.container(border=True):
                st.markdown(f"**{owner['titulo']}**")
                st.markdown(f"### {owner['nombre']}")
                st.caption(owner["detalle"])

    tab_resumen, tab_arquitectura, tab_hitos, tab_roles = st.tabs(
        ["Resumen", "Arquitectura", "Hitos", "Roles"]
    )

    with tab_resumen:
        st.markdown("#### Vision general")
        st.write(
            "MediCare Enterprise PRO es un ERP/POS para internacion domiciliaria, ambulancias y auditoria clinica. "
            "Hoy funciona como una SPA reactiva en Python con Streamlit y un modelo de persistencia hibrido optimizado "
            "para movilidad, velocidad y trabajo en condiciones de conectividad variable."
        )

        col_res_1, col_res_2 = st.columns(2)
        with col_res_1:
            with st.container(border=True):
                st.markdown("**Profesionales objetivo**")
                st.write(
                    "Esta plataforma apunta a medicos, enfermeros, kinesiologos y a directores o dueños de clinicas "
                    "de internacion domiciliaria."
                )
        with col_res_2:
            with st.container(border=True):
                st.markdown("**Cobertura multiplataforma**")
                st.write(
                    "El sistema esta pensado para smartphone, tablet y PC desde navegador, sin instalar software adicional."
                )

        _render_listado("Objetivos actuales de migracion", MIGRATION_OBJECTIVES)
        _render_listado("Metodologia de trabajo", WORK_METHOD)

    with tab_arquitectura:
        st.markdown("#### Estado actual y destino")
        col_actual, col_destino = st.columns(2)

        with col_actual:
            with st.container(border=True):
                _render_listado("Stack actual", CURRENT_STACK)

        with col_destino:
            with st.container(border=True):
                _render_listado("Arquitectura objetivo", TARGET_ARCHITECTURE)

        st.info(
            "Python no desaparece: queda como motor estrategico para inteligencia clinica, analitica avanzada, "
            "procesamiento pesado y reutilizacion del core ya validado en produccion."
        )

        with st.container(border=True):
            st.markdown("**Estrategia de coexistencia tecnologica**")
            st.write(
                "La migracion adopta una arquitectura poliglota. NestJS se enfoca en trafico, seguridad y persistencia "
                "relacional, mientras Python conserva el core clinico, el procesamiento de vademecum, la geolocalizacion "
                "y las analiticas avanzadas. El objetivo es transicionar sin cortar servicio."
            )

    with tab_hitos:
        st.markdown("#### Roadmap")
        mostrar_dataframe_con_scroll(pd.DataFrame(MILESTONES), height=330)

        with st.container(border=True):
            st.markdown("**Lectura operativa**")
            st.write(
                "La secuencia definida prioriza primero base de datos, seguridad y reglas de acceso; despues motor "
                "operativo; y por ultimo la experiencia visual completa. Eso reduce riesgo y evita rehacer logica critica."
            )

    with tab_roles:
        st.markdown("#### Matriz de roles del documento")
        st.caption(
            "Nota: en la app actual el rol operativo administrativo figura como `Administrativo`; en el documento aparece como `Administrador`."
        )
        mostrar_dataframe_con_scroll(pd.DataFrame(ROLE_MATRIX), height=430)

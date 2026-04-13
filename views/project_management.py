import pandas as pd
import streamlit as st

from core.jira_status import fetch_jira_issues, jira_setup_hint, load_jira_config
from core.view_helpers import bloque_mc_grid_tarjetas
from core.utils import mostrar_dataframe_con_scroll


DOC_URL = "https://docs.google.com/document/d/1D8Gh4VWW_zHDbBw26c23PxxwR4ImjoMJAbYveINKhUI/edit?usp=sharing"
DOC_REVISION = "Documento de referencia: 1 de abril de 2026"

OWNERS = [
    {
        "titulo": "Creador y propietario del producto",
        "nombre": "Enzo Girardi",
        "detalle": "Define reglas de negocio, alcance clinico y prioridades del producto.",
    },
    {
        "titulo": "Socio tecnico y arquitecto",
        "nombre": "Dario Lanfranco",
        "detalle": "Lidera la migracion silenciosa y la arquitectura escalable (NestJS, Angular, convivencia con Python).",
    },
]

CURRENT_STACK = [
    "Lenguaje: Python 3.x.",
    "Framework core (frontend y backend): Streamlit renderiza la UI en tiempo real y la logica de servidor en una SPA reactiva.",
    "UI enterprise: componentes Streamlit + CSS (tarjetas flotantes, botones con relieve, bloqueo de pull-to-refresh en moviles donde aplica).",
    "Base de datos (BaaS): Supabase (PostgreSQL + REST API).",
    "Procesamiento: Pandas para manipular colecciones, cruzar informacion clinica, grillas y exportes a Excel.",
    "PDF: FPDF como motor principal on-the-fly (historias clinicas, consentimientos, recibos de caja); otros modulos pueden usar ReportLab u hojas de estilo equivalentes.",
    "Graficos: Altair para curvas pediatricas, barras de rendimiento de enfermeria y visualizaciones vectoriales interactivas.",
    "GPS: streamlit-geolocation (API del navegador) + Nominatim (OpenStreetMap) para reverse geocoding en check-in / check-out.",
    "Firmas: streamlit-drawable-canvas + Pillow (trazos a pixeles, fondo para almacenamiento); imagenes y adjuntos en Base64 dentro del JSON en Supabase (sin buckets externos por ahora).",
]

HYBRID_STATE = [
    "Cache en memoria: la aplicacion vive en `st.session_state`. Al iniciar sesion se descarga la base y se aloja en listas y diccionarios locales (ej. pacientes_db, vitales_db, administracion_med_db) para navegacion, filtros y calculos sin queries constantes al servidor.",
    "Persistencia documental (patron NoSQL sobre SQL): en Supabase la tabla `medicare_db`; `guardar_datos()` empaqueta el `session_state` en un JSON y hace upsert en un unico registro (id = 1).",
]

TARGET_ARCHITECTURE = [
    "Frontend: Angular (SPA modular, TypeScript, UX rapida sin recargas completas por vista).",
    "Backend de trafico: NestJS sobre Node.js (JWT, guards, escalado por microservicios cuando haga falta).",
    "Base: Supabase como almacen comun durante la coexistencia con Streamlit.",
    "Python: motor de inteligencia clinica, vademecum, geocodificacion pesada y analitica avanzada (microservicios asincronicos).",
    "Arquitectura poliglota: transicion sin cortar operacion; se reutiliza la logica validada en produccion.",
]

MIGRATION_OBJECTIVES = [
    "Migracion silenciosa: el producto sigue operando mientras se construye un motor mas potente adentro.",
    "Escalar a 100 o 1.000 usuarios concurrentes (ej. 500 enfermeros de 20 clinicas) sin colapsar el servicio.",
    "Optimizar recursos y consumo de datos en moviles con senal inestable.",
    "Garantizar rapidez, seguridad y cero perdida de datos.",
]

ANGULAR_ADVANTAGES = [
    "Modularidad y escalabilidad: componentes reutilizables (MAR, dashboard de auditoria, etc.).",
    "SPA: navegacion instantanea; el medico no espera recargas completas al cambiar de paciente (mejor UX).",
    "TypeScript: menos errores en ejecucion (ej. dosis numerica vs texto).",
    "Mantenibilidad: estructura de archivos estandar para incorporar desarrolladores rapido.",
]

NESTJS_ADVANTAGES = [
    "Microservicios: si Facturacion crece, se puede separar sin romper el resto.",
    "Seguridad out-of-the-box: JWT y guards para datos sensibles de pacientes.",
    "Eficiencia de Node.js: I/O no bloqueante para miles de check-ins GPS o cargas de signos vitales.",
    "Inyeccion de dependencias y testing automatico para reducir fallos post-actualizacion.",
]

PYTHON_STRATEGIC = [
    "Motor de inteligencia clinica: prediccion de descompensaciones, graficos complejos de auditoria, microservicios Python asincronicos para datos pesados.",
    "NestJS gestiona usuarios y trafico; Python procesa analitica y core clinico especializado.",
]

MILESTONES = [
    {
        "Hito": "1. Cimientos y Cerebro",
        "Ventana": "Mes 1",
        "Accion": "Configurar el proyecto en NestJS y conectar Prisma con la base de Supabase (antes de tocar el frente).",
        "Tarea Enzo": "Entregar el diccionario limpio de medicamentos y reglas de negocio (ej. que pasa si un enfermero se olvida de fichar).",
        "Resultado": "Base normalizada: pacientes, visitas, usuarios y medicamentos lista para miles de registros.",
    },
    {
        "Hito": "2. Puerta de Entrada y Seguridad",
        "Ventana": "Mes 2",
        "Accion": "Sistema de login y roles (Superadmin, Admin, Coordinador y Usuario) en el backend enterprise.",
        "Tarea Enzo": "Definir que puede ver cada uno (ej. el enfermero no ve cuanto factura la clinica).",
        "Resultado": "Login disenado funcionando de verdad; solo entran autorizados.",
    },
    {
        "Hito": "3. Corazon Operativo",
        "Ventana": "Mes 3-4",
        "Accion": "En NestJS: logica de visitas y GPS; endpoints para que el movil envie ubicacion y quede guardada. Integracion con Python para mapas o estadisticas de visitas.",
        "Tarea Enzo": "Priorizar con equipo clinico que migrar primero en campo.",
        "Resultado": "Visitas cargadas en el nuevo edificio (backend NestJS + servicios Python donde aplique).",
    },
    {
        "Hito": "4. Estetica",
        "Ventana": "Mes 5",
        "Accion": "Angular: dashboard en tiempo real para el dueno (deudores, visitas hechas, alertas medicas).",
        "Tarea Enzo": "Aceptacion de producto y salida controlada.",
        "Resultado": "Lanzamiento de la version MediCare PRO.",
    },
]

ROLE_MATRIX = [
    {"Categoria": "Sistema", "Modulo": "Panel Global (Clinicas)", "SuperAdmin": "Si", "Coordinador": "No", "Operativo": "No", "Administrador": "No"},
    {"Categoria": "Sistema", "Modulo": "Gestion de Equipo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "No"},
    {"Categoria": "Sistema", "Modulo": "Auditoria General", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "No"},
    {"Categoria": "Sistema", "Modulo": "Auditoria Legal", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "No"},
    {"Categoria": "Gestion", "Modulo": "Admision (Pacientes)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Parcial (carga)", "Administrador": "Si"},
    {"Categoria": "Gestion", "Modulo": "Dashboard Ejecutivo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "Si"},
    {"Categoria": "Gestion", "Modulo": "Red de Profesionales", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "Si"},
    {"Categoria": "Gestion", "Modulo": "Telemedicina", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Visitas y Agenda", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "Si"},
    {"Categoria": "Clinica", "Modulo": "Historial (HC)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Signos Vitales", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Evolucion Medica", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Recetas / Medicacion", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Estudios / Ordenes", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Escalas Clinicas", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Pediatria (Curvas)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Balance Hidrico", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Emergencias", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Clinica", "Modulo": "Alertas app paciente", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "No"},
    {"Categoria": "Logistica", "Modulo": "Materiales (Gasto)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "Si"},
    {"Categoria": "Logistica", "Modulo": "Inventario / Stock", "SuperAdmin": "Si", "Coordinador": "No", "Operativo": "No", "Administrador": "Si"},
    {"Categoria": "Contable", "Modulo": "Caja Diaria", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Solo hoy", "Administrador": "Si"},
    {"Categoria": "Contable", "Modulo": "Cierre Diario", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "Si"},
    {"Categoria": "Contable", "Modulo": "Asistencia en Vivo", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "Si"},
    {"Categoria": "Contable", "Modulo": "Control RRHH (GPS)", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "No", "Administrador": "Si"},
    {"Categoria": "Output", "Modulo": "Centro PDF", "SuperAdmin": "Si", "Coordinador": "Si", "Operativo": "Si", "Administrador": "Si"},
]

WORK_METHOD = [
    "Sprints diarios: comunicacion por WhatsApp y Slack.",
    "Jira o Trello: tablero simple — Por hacer (pendientes) | En proceso (codigo del momento) | Para revisar (veredicto final Enzo) | Listo.",
    "En esta app, la pestaña Jira puede listar issues si configurás secrets.",
    "Reglas de negocio y validaciones explicitas antes de cada migracion.",
]

MAR_SUMMARY = [
    "MAR: sabana de enfermeria matricial 24 h con `st.data_editor` (Pandas), trazabilidad algoritmica de horas y vencimiento de recetas (`datetime`).",
    "Estados Realizado / No realizado con justificacion obligatoria cuando corresponde.",
]

BUSINESS_MODULES = [
    "Inventario y caja: logica transaccional — consumo en domicilio descuenta stock en tiempo real; caja con entradas/pendientes y recibos descargables por operador y empresa.",
    "Control de accesos: login en sesion con roles (SuperAdmin, Coordinador, Operativo en el nucleo del documento); la matriz suma Administrador para modulos de gestion y contable. Filtrado de vistas, pacientes y datos financieros por clinica/empresa.",
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
            <h2 class="mc-hero-title">Gestion de proyecto MediCare Enterprise PRO</h2>
            <p class="mc-hero-text">ERP/POS para internacion domiciliaria, ambulancias y auditoria clinica. Documento vivo de producto, arquitectura y roadmap de la migracion silenciosa.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Streamlit + Supabase</span>
                <span class="mc-chip">Angular + NestJS (objetivo)</span>
                <span class="mc-chip">Roles y Jira</span>
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
        f"{DOC_REVISION}. Fuente: [Google Docs]({DOC_URL}). Rol en sesion: `{rol or 'Sin rol'}`."
    )
    bloque_mc_grid_tarjetas(
        [
            ("Resumen", "Producto actual, stack, MAR y objetivos de migracion."),
            ("Arquitectura y hitos", "Diseno objetivo NestJS/Angular y cronograma por meses."),
            ("Roles y Jira", "Matriz de accesos por modulo; pestaña Jira opcional con API."),
        ]
    )
    st.caption(
        "Esta pantalla es documentacion interna: no modifica pacientes ni datos operativos. Usala para alinear equipo y proveedores."
    )

    col_owner_1, col_owner_2 = st.columns(2)
    for col, owner in zip((col_owner_1, col_owner_2), OWNERS):
        with col:
            with st.container(border=True):
                st.markdown(f"**{owner['titulo']}**")
                st.markdown(f"### {owner['nombre']}")
                st.caption(owner["detalle"])

    tab_resumen, tab_arquitectura, tab_hitos, tab_roles, tab_jira = st.tabs(
        ["Resumen", "Arquitectura", "Hitos", "Roles", "Jira"]
    )

    with tab_resumen:
        st.markdown("#### Descripcion general del proyecto actual")
        st.write(
            "MediCare Enterprise PRO es un sistema ERP/POS orientado a la gestion de internacion domiciliaria, "
            "ambulancias y auditoria clinica. Esta desarrollado como una Single-Page Application (SPA) reactiva "
            "unificando frontend y servidor en Python con Streamlit, con UI enterprise mediante componentes nativos "
            "y CSS personalizado."
        )

        col_res_1, col_res_2 = st.columns(2)
        with col_res_1:
            with st.container(border=True):
                st.markdown("**¿Hacia que profesionales va dirigido?**")
                st.write(
                    "Medicos, enfermeros, kinesiologos y directores o duenos de clinicas e instituciones de "
                    "internacion domiciliaria."
                )
        with col_res_2:
            with st.container(border=True):
                st.markdown("**¿Es multiplataforma?**")
                st.write(
                    "Si: plataforma web; no hace falta instalar apps raras. Navegador (Chrome, Safari, etc.) en Android, iPhone, "
                    "tablet o PC. Con internet, la clinica queda en el bolsillo."
                )

        _render_listado("Arquitectura y estado (persistencia hibrida)", HYBRID_STATE)
        _render_listado("Stack tecnologico principal (hoy)", CURRENT_STACK)
        _render_listado("MAR (Medication Administration Record)", MAR_SUMMARY)
        _render_listado("Otros modulos de negocio", BUSINESS_MODULES)
        _render_listado("Objetivo de la migracion silenciosa", MIGRATION_OBJECTIVES)
        _render_listado("Metodologia de trabajo", WORK_METHOD)

    with tab_arquitectura:
        st.markdown("#### Como lo hacemos realidad: frente y motor")
        st.write(
            "Se separa la estetica (Angular, lo que ve el medico) del motor (NestJS sobre Node.js para trafico, "
            "seguridad y persistencia relacional). La base sigue siendo Supabase. Python permanece como motor "
            "estrategico para core clinico pesado, vademecum, geolocalizacion y analitica."
        )

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            with st.container(border=True):
                _render_listado("Ventajas de Angular (frontend)", ANGULAR_ADVANTAGES)
        with col_a2:
            with st.container(border=True):
                _render_listado("Ventajas de NestJS (backend)", NESTJS_ADVANTAGES)

        with st.container(border=True):
            _render_listado("Rol estrategico de Python", PYTHON_STRATEGIC)

        st.info(
            "Coexistencia tecnologica (arquitectura poliglota): NestJS gestiona trafico, seguridad y persistencia relacional; "
            "Python se especializa en core clinico — vademecum, geolocalizacion inversa y analiticas avanzadas — "
            "aprovechando algoritmos ya desarrollados (fase V9.11). Transicion fluida sin cortar servicio."
        )

        with st.container(border=True):
            _render_listado("Arquitectura objetivo (resumen)", TARGET_ARCHITECTURE)

    with tab_hitos:
        st.markdown("#### Hitos del roadmap")
        mostrar_dataframe_con_scroll(pd.DataFrame(MILESTONES), height=380)

        with st.container(border=True):
            st.markdown("**Lectura operativa**")
            st.write(
                "Primero base y modelo de datos; luego seguridad y roles; despues visitas/GPS y endpoints operativos; "
                "al final experiencia Angular y dashboard ejecutivo. Reduce riesgo y evita rehacer logica critica."
            )

    with tab_roles:
        st.markdown("#### Roles dentro de MediCare Enterprise PRO")
        st.caption(
            "Columna **Administrador** = hoy unificada en rol **Operativo** (perfil de gestion en ficha). "
            "El menu y el acceso por modulo siguen `MODULO_ROLES_PERMITIDOS` en `core/view_roles.py` (alineado a esta matriz). "
            "El **plan de enfermeria** (UPP, caidas, incidentes) esta integrado en **Evolucion** como pestaña; no hay modulo separado en el menu. "
            "Acciones finas (recetas, PDF, etc.) en `ACTION_ROLE_RULES` en `core/utils.py`. "
            "[Documento fuente](%s)."
            % DOC_URL
        )
        mostrar_dataframe_con_scroll(pd.DataFrame(ROLE_MATRIX), height=460)

    with tab_jira:
        st.markdown("#### Backlog y tablero (Jira Cloud)")
        st.caption(
            "Vista de solo lectura para dar contexto al equipo sin salir de MediCare. "
            "Los cambios de estado se hacen en Jira (o Trello, segun metodologia del documento)."
        )
        jira_cfg = load_jira_config()
        if not jira_cfg:
            st.info(jira_setup_hint())
            st.markdown(
                "- Creá un API token en tu cuenta Atlassian: "
                "[Security / API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).\n"
                "- Usá el correo con el que ingresás a Jira y el token como contraseña (autenticación Basic en la API).\n"
                "- El `jql` filtra qué issues se listan (proyecto, sprint, etiqueta, etc.)."
            )
        else:
            if jira_cfg.get("board_url"):
                st.link_button("Abrir tablero en Jira", jira_cfg["board_url"], use_container_width=False)
            st.code(jira_cfg["jql"], language="text")
            with st.spinner("Consultando Jira..."):
                filas, err = fetch_jira_issues(jira_cfg)
            if err:
                st.warning(f"No se pudieron obtener los issues: {err}")
            elif not filas:
                st.info("El JQL no devolvió issues. Ajustá la consulta en secrets o revisá permisos del usuario del token.")
            else:
                df_j = pd.DataFrame(filas)
                with st.container(border=True):
                    st.dataframe(
                        df_j,
                        use_container_width=True,
                        hide_index=True,
                        height=min(420, 80 + len(df_j) * 36),
                        column_config={
                            "URL": st.column_config.LinkColumn("Enlace", display_text="Abrir"),
                        },
                    )

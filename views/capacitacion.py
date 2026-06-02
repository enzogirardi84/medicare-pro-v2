"""Módulo de capacitación interactiva — guía dinámica de todos los módulos."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.app_logging import log_event

# ─── Datos de capacitación ───────────────────────────────────────────────

CAPACITACION: dict[str, dict[str, Any]] = {
    "Dashboard": {
        "emoji": "📊",
        "desc": "Visión ejecutiva con KPIs, gráficos semanales, calendario heatmap y mapa de visitas GPS.",
        "tiempo": "5 min",
        "pasos": [
            "Al iniciar sesión, el Dashboard es tu pantalla principal.",
            "Observá los KPIs superiores: pacientes activos, visitas del día, urgencias.",
            "Desplazate hacia abajo para ver el heatmap de actividad de los últimos 30 días.",
            "El mapa geográfico muestra la ubicación de cada visita del día.",
            "Usá el selector de fechas para filtrar el período.",
        ],
        "tips": ["Los KPIs se actualizan en tiempo real con cada nueva visita o carga de datos."],
    },
    "Visitas y Agenda": {
        "emoji": "📅",
        "desc": "Planificación, asignación y fichado GPS de visitas domiciliarias.",
        "tiempo": "8 min",
        "pasos": [
            "Andá a Visitas y Agenda desde el menú lateral.",
            "Usá el calendario para seleccionar el día. Las visitas asignadas aparecen en la línea de tiempo.",
            "Creá una nueva visita: seleccioná paciente, profesional, fecha y hora.",
            "El profesional recibe la visita en su móvil con la dirección y datos del paciente.",
            "Al llegar, el profesional fichá con GPS: queda registrada la ubicación y hora exacta.",
            "Completada la visita, el profesional puede cargar evolución, fotos y formularios.",
        ],
        "tips": [
            "Las visitas pendientes se marcan en color. Las atrasadas aparecen en rojo.",
            "Podés reasignar una visita arrastrándola a otro profesional en el calendario.",
        ],
    },
    "Historia Clínica": {
        "emoji": "📋",
        "desc": "Registro clínico digital: admisión, vitales, evolución, estudios, escalas y más.",
        "tiempo": "10 min",
        "pasos": [
            "Seleccioná un paciente desde el selector superior.",
            "Andá a Historia Clínica en el menú.",
            "La solapa 'Admisión' contiene los datos filiatorios y de contacto del paciente.",
            "En 'Evolución' se carga el registro diario: texto libre más signos vitales.",
            "Las 'Escalas Clínicas' permiten evaluar riesgo de úlceras, dolor, caídas, etc.",
            "Los 'Estudios' agrupan resultados de laboratorio e imágenes.",
            "El 'Balance' y 'Percentilo' son específicos para pacientes pediátricos.",
        ],
        "tips": [
            "Todos los cambios quedan registrados en la auditoría legal del sistema.",
            "Podés generar un PDF ejecutivo de la historia clínica desde el botón 'Exportar'.",
        ],
    },
    "Recetas": {
        "emoji": "💊",
        "desc": "Prescripción, administración y stock de medicamentos con alertas de interacciones.",
        "tiempo": "7 min",
        "pasos": [
            "Andá a Recetas desde el menú lateral con un paciente seleccionado.",
            "La solapa 'Prescribir' te permite crear una nueva receta médica.",
            "Buscá el medicamento por nombre en el vademécum integrado (>50 fármacos).",
            "Especificá dosis, frecuencia, duración y vía de administración.",
            "La receta queda firmada digitalmente y se puede imprimir o enviar.",
            "La solapa 'MAR' muestra el plan de administración por turno y medicamento.",
            "La solapa 'Stock' lleva el control de existencias con alertas de vencimiento.",
        ],
        "tips": [
            "El sistema alerta automáticamente sobre interacciones medicamentosas.",
            "La calculadora de dosis pediátricas está disponible desde el menú principal.",
        ],
    },
    "Emergencias": {
        "emoji": "🚨",
        "desc": "Triage, gestión de llamados, alertas a profesionales y respuesta coordinada.",
        "tiempo": "5 min",
        "pasos": [
            "Andá a Emergencias desde el menú lateral.",
            "Registrá un nuevo evento seleccionando paciente y nivel de prioridad.",
            "El sistema envía alerta automática a los profesionales disponibles.",
            "Podés hacer seguimiento del tiempo de respuesta y resolución.",
            "Cada emergencia queda documentada con fecha, hora y actuación profesional.",
        ],
        "tips": [
            "Las emergencias con prioridad alta se muestran en rojo en el dashboard.",
            "El módulo se integra con la app del paciente para alertas en tiempo real.",
        ],
    },
    "Telemedicina": {
        "emoji": "📹",
        "desc": "Sala de teleconsulta remota con acceso a historia clínica del paciente.",
        "tiempo": "4 min",
        "pasos": [
            "Seleccioná un paciente y andá a Telemedicina.",
            "Iniciá una nueva sesión. El paciente recibe un enlace para unirse.",
            "Durante la consulta, tenés acceso a los datos del paciente.",
            "Podés cargar indicaciones y recetas durante o después de la consulta.",
        ],
        "tips": [
            "La sala queda grabada si es necesario para auditoría (requiere configuración).",
        ],
    },
    "RRHH y Fichajes": {
        "emoji": "👥",
        "desc": "Gestión del equipo: profesionales, fichajes, presentismo y guardias.",
        "tiempo": "6 min",
        "pasos": [
            "Andá a RRHH y Fichajes desde el menú.",
            "La solapa 'Equipo' muestra todos los profesionales dados de alta.",
            "Podés agregar, editar o desactivar profesionales desde esta pantalla.",
            "La solapa 'Fichajes' registra las entradas y salidas de cada profesional.",
            "Los reportes de presentismo se pueden exportar a PDF.",
        ],
        "tips": [
            "Cada profesional tiene un rol que determina a qué módulos accede.",
            "Los fichajes pueden integrarse con la geolocalización de visitas.",
        ],
    },
    "Caja": {
        "emoji": "💰",
        "desc": "Registro de cobros, comprobantes, libro diario y cierre de caja.",
        "tiempo": "5 min",
        "pasos": [
            "Andá a Caja desde el menú lateral.",
            "Registrá un nuevo comprobante seleccionando tipo (factura, recibo, nota de crédito).",
            "El libro diario se actualiza automáticamente con cada movimiento.",
            "Al final del día, ejecutá el cierre de caja para verificar el balance.",
        ],
        "tips": [
            "La caja se integra con la facturación electrónica vía API.",
            "Los comprobantes se pueden anular pero quedan registrados en auditoría.",
        ],
    },
    "Inventario": {
        "emoji": "📦",
        "desc": "Control de stock de insumos, materiales y medicamentos con alertas de reposición.",
        "tiempo": "5 min",
        "pasos": [
            "Andá a Inventario desde el menú lateral.",
            "Agregá productos con nombre, categoría, cantidad mínima y precio.",
            "El sistema marca automáticamente los productos por debajo del umbral.",
            "Podés registrar ingresos y egresos de stock con fecha y responsable.",
        ],
        "tips": [
            "Configurá alertas de reposición para no quedarte sin insumos críticos.",
        ],
    },
    "Auditoría": {
        "emoji": "🔍",
        "desc": "Trazabilidad legal completa de cada acción en el sistema.",
        "tiempo": "4 min",
        "pasos": [
            "Andá a Auditoría desde el menú lateral.",
            "Buscá eventos por fecha, usuario, paciente o tipo de acción.",
            "Cada entrada muestra: quién, qué, cuándo, dónde y desde qué dispositivo.",
            "Podés exportar reportes de auditoría firmados digitalmente.",
        ],
        "tips": [
            "La auditoría es inviolable: los registros no se pueden modificar ni eliminar.",
            "Ideal para presentar ante inspecciones o requerimientos legales.",
        ],
    },
    "Chatbot IA": {
        "emoji": "🤖",
        "desc": "Asistente clínico inteligente con acceso a datos del paciente y búsqueda web.",
        "tiempo": "3 min",
        "pasos": [
            "Andá a Chatbot IA desde el menú.",
            "Escribí tu consulta en lenguaje natural (ej: 'dosis de ibuprofeno para niño de 20kg').",
            "El chatbot busca en la farmacopea, en los datos del paciente y en web.",
            "Siempre verificá la información con fuentes oficiales antes de actuar.",
        ],
        "tips": [
            "El chatbot NO reemplaza el criterio médico. Siempre verificá las respuestas.",
        ],
    },
    "App Paciente": {
        "emoji": "📱",
        "desc": "Aplicación para que los pacientes accedan a su información y se comuniquen.",
        "tiempo": "4 min",
        "pasos": [
            "Configurá el acceso del paciente desde el panel de alertas.",
            "El paciente puede ver su historia, turnos, recetas y enviar mensajes.",
            "Las alertas se envían automáticamente (recordatorios, cambios de turno).",
        ],
        "tips": [
            "La app del paciente está disponible como PWA (no requiere instalación).",
        ],
    },
}

CATEGORIAS_CAPACITACION: dict[str, list[str]] = {
    "Primeros pasos": ["Dashboard"],
    "Gestión clínica": ["Historia Clínica", "Recetas", "Emergencias"],
    "Operaciones": ["Visitas y Agenda", "Telemedicina", "App Paciente"],
    "Administración": ["Caja", "RRHH y Fichajes", "Inventario"],
    "Legal y soporte": ["Auditoría", "Chatbot IA"],
}


def _render_busqueda(filtro: str) -> list[str]:
    """Filtra módulos por texto de búsqueda."""
    if not filtro:
        return list(CAPACITACION.keys())
    filtro = filtro.lower()
    result = []
    for nombre, datos in CAPACITACION.items():
        if (filtro in nombre.lower()
                or filtro in datos["emoji"]
                or filtro in datos["desc"].lower()):
            result.append(nombre)
    return result


def _render_modulo(nombre: str, datos: dict[str, Any]) -> None:
    """Renderiza el contenido completo de un módulo de capacitación."""
    with st.container():
        st.markdown(f"### {datos['emoji']} {nombre}")
        st.caption(f"⏱️ {datos['tiempo']} de lectura")
        st.write(datos["desc"])

        st.markdown("#### 📖 Guía paso a paso")
        for i, paso in enumerate(datos["pasos"], 1):
            st.markdown(f"**{i}.** {paso}")

        if datos.get("tips"):
            st.markdown("#### 💡 Tips")
            for tip in datos["tips"]:
                st.info(tip)

        # Marcar como completado
        if st.button(f"✅ Marcar como leído — {nombre}",
                     key=f"completar_{nombre}", use_container_width=True):
            completados = set(st.session_state.get("capacitacion_completados", []))
            completados.add(nombre)
            st.session_state.capacitacion_completados = list(completados)
            log_event("capacitacion", f"Modulo completado: {nombre}")
            st.rerun()


def render_capacitacion(paciente_sel: Any, mi_empresa: Any, user: Any, rol: str) -> None:
    """Módulo de capacitación interactiva."""
    st.title("🎓 Capacitación Interactiva")

    # Inicializar estado
    completados = set(st.session_state.get("capacitacion_completados", []))
    busqueda = st.session_state.get("capacitacion_busqueda", "")

    tab_intro, tab_guias, tab_progreso = st.tabs([
        "📖 Introducción", "📚 Guías por módulo", "📊 Mi progreso"
    ])

    # ── TAB 1: Introducción ─────────────────────────────────────────
    with tab_intro:
        st.markdown("""
        ### Bienvenido a MediCare Enterprise PRO

        Este módulo de capacitación te guiará a través de todos los módulos
        de la plataforma. Podés aprender a tu ritmo, marcar temas como completados
        y seguir tu progreso general.

        **¿Por dónde empezar?**
        - Si sos **nuevo**, comenzá por **Dashboard** y **Visitas y Agenda**.
        - Si ya conocés lo básico, explorá los módulos específicos de tu área.
        - Usá la **búsqueda** para encontrar rápido lo que necesitás.
        """)

        st.markdown("### 🔍 Acceso rápido")
        cols = st.columns(3)
        modulos_rapidos = ["Dashboard", "Visitas y Agenda", "Historia Clínica",
                           "Recetas", "Emergencias", "Caja"]
        for i, nombre in enumerate(modulos_rapidos):
            datos = CAPACITACION.get(nombre)
            if not datos:
                continue
            with cols[i % 3]:
                if st.button(
                    f"{datos['emoji']} {nombre}",
                    key=f"rapido_{nombre}",
                    use_container_width=True,
                ):
                    st.session_state.capacitacion_modulo_actual = nombre
                    st.rerun()

    # ── TAB 2: Guías ────────────────────────────────────────────────
    with tab_guias:
        # Búsqueda
        busqueda = st.text_input(
            "🔎 Buscar módulo...",
            value=busqueda,
            placeholder="Ej: recetas, emergencias, caja...",
            key="capacitacion_busqueda_input",
        )
        if busqueda != st.session_state.get("capacitacion_busqueda", ""):
            st.session_state.capacitacion_busqueda = busqueda
            st.rerun()

        modulos_filtrados = _render_busqueda(busqueda)

        if not modulos_filtrados:
            st.warning("No se encontraron módulos con ese criterio de búsqueda.")
            return

        # Si hay un módulo específico seleccionado, mostrarlo
        modulo_actual = st.session_state.get("capacitacion_modulo_actual")
        if modulo_actual and modulo_actual in modulos_filtrados:
            datos = CAPACITACION.get(modulo_actual)
            if datos:
                _render_modulo(modulo_actual, datos)
                if st.button("← Volver al listado", use_container_width=True):
                    del st.session_state.capacitacion_modulo_actual
                    st.rerun()
                return

        # Mostrar por categorías
        for categoria, modulos in CATEGORIAS_CAPACITACION.items():
            modulos_visibles = [m for m in modulos if m in modulos_filtrados]
            if not modulos_visibles:
                continue

            st.markdown(f"#### {categoria}")
            cols = st.columns(2)
            for i, nombre in enumerate(modulos_visibles):
                datos = CAPACITACION.get(nombre)
                if not datos:
                    continue
                leido = "✅ " if nombre in completados else ""
                with cols[i % 2]:
                    st.button(
                        f"{leido}{datos['emoji']} **{nombre}**  \n{datos['desc'][:60]}..."
                        + (f"  \n⏱️ {datos['tiempo']}"),
                        key=f"mod_{nombre}",
                        use_container_width=True,
                        help="Hacé clic para ver la guía completa",
                        on_click=lambda n=nombre: (
                            st.session_state.update(
                                {"capacitacion_modulo_actual": n})
                        ),
                    )

    # ── TAB 3: Progreso ─────────────────────────────────────────────
    with tab_progreso:
        total = len(CAPACITACION)
        leidos = len(completados)
        porcentaje = round(leidos / total * 100) if total else 0

        st.markdown(f"### 📊 Progreso general")
        st.progress(porcentaje / 100, text=f"{porcentaje}% completado")

        col1, col2, col3 = st.columns(3)
        col1.metric("Módulos totales", total)
        col2.metric("Completados", leidos)
        col3.metric("Pendientes", total - leidos)

        if completados:
            st.markdown("#### ✅ Módulos completados")
            for nombre in sorted(completados):
                datos = CAPACITACION.get(nombre, {})
                st.success(f"{datos.get('emoji', '📘')} {nombre}")

        if total - leidos > 0:
            st.markdown("#### 📚 Módulos pendientes")
            cols = st.columns(3)
            i = 0
            for nombre in CAPACITACION:
                if nombre not in completados:
                    datos = CAPACITACION.get(nombre, {})
                    with cols[i % 3]:
                        if st.button(
                            f"{datos.get('emoji', '📘')} {nombre}",
                            key=f"pendiente_{nombre}",
                            use_container_width=True,
                        ):
                            st.session_state.capacitacion_modulo_actual = nombre
                            st.rerun()
                    i += 1

        if completados:
            if st.button("🔄 Reiniciar progreso", use_container_width=True,
                         type="secondary"):
                st.session_state.capacitacion_completados = []
                log_event("capacitacion", "Progreso reiniciado")
                st.rerun()

from core.alert_toasts import queue_toast
import base64
from uuid import uuid4

import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, optimizar_imagen_bytes, puede_accion, seleccionar_limite_registros, parse_fecha_hora


def _mismo_estudio(registro, objetivo):
    if registro.get("id") and objetivo.get("id"):
        return registro.get("id") == objetivo.get("id")
    return (
        registro.get("paciente") == objetivo.get("paciente")
        and registro.get("fecha") == objetivo.get("fecha")
        and registro.get("tipo") == objetivo.get("tipo")
        and registro.get("detalle") == objetivo.get("detalle")
        and registro.get("firma") == objetivo.get("firma")
    )


def render_estudios(paciente_sel, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "estudios_registrar")
    puede_borrar = puede_accion(rol, "estudios_borrar")

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Estudios complementarios</h2>
            <p class="mc-hero-text">Ordenes y resultados con adjunto opcional (foto, PDF o camara). Pensado para cargar rapido en domicilio con trazabilidad por profesional.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Laboratorio / imagenes</span>
                <span class="mc-chip">Adjuntos</span>
                <span class="mc-chip">Permisos por rol</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Pedidos y resultados", "Unifica laboratorio e imagenes en un solo legajo."),
            ("Adjuntos", "Subi foto, PDF o captura desde la camara."),
            ("Permisos", "Algunas acciones dependen del rol asignado."),
        ]
    )
    st.caption(
        "Si tu rol permite cargar, el formulario queda arriba; debajo, herramientas de borrado acotadas y el listado con limite ajustable. Activa **Cargar imagenes** solo si necesitas ver adjuntos (ahorra memoria)."
    )

    if puede_registrar:
        with st.form("form_estudios", clear_on_submit=True):
            col_e1, col_e2 = st.columns([1, 2])
            tipo_estudio = col_e1.selectbox("Tipo de Estudio", [
                "Laboratorio (Sangre/Orina)", "Radiografia (Rx)", "Ecografia",
                "Electrocardiograma (ECG)", "Tomografia (TAC)", "Resonancia Magnetica (RMN)", "Otro"
            ])
            detalle_estudio = col_e2.text_input("Detalle del Pedido o Resultado")

            st.markdown("##### Adjuntar Documento (Opcional)")
            archivo_subido = st.file_uploader("Subir archivo, foto de galeria o PDF", type=["png", "jpg", "jpeg", "pdf"], key="uploader_estudio")

            mostrar_cam_estudio = st.checkbox(
                "Mostrar opcion de tomar foto con la camara ahora",
                value=False,
                key="mostrar_cam_estudio_form",
            )
            foto_estudio = None
            if mostrar_cam_estudio:
                usar_cam = st.checkbox("Activar camara", key="activar_cam_estudio_form")
                if usar_cam:
                    foto_estudio = st.camera_input("Tomar foto en vivo", key="camara_estudio")

            if st.form_submit_button("Guardar Estudio Clinico", use_container_width=True, type="primary"):
                img_b64 = ""
                ext = ""
                if archivo_subido is not None:
                    raw_bytes = archivo_subido.getvalue()
                    ext = archivo_subido.name.split('.')[-1].lower()
                    if ext in ["png", "jpg", "jpeg"]:
                        raw_bytes, ext_optimizada = optimizar_imagen_bytes(raw_bytes)
                        ext = ext_optimizada or ext
                    img_b64 = base64.b64encode(raw_bytes).decode("utf-8")
                elif foto_estudio is not None:
                    raw_bytes, ext_optimizada = optimizar_imagen_bytes(foto_estudio.getvalue())
                    img_b64 = base64.b64encode(raw_bytes).decode("utf-8")
                    ext = ext_optimizada or "jpg"

                st.session_state.setdefault("estudios_db", [])
                st.session_state["estudios_db"].append({
                    "id": str(uuid4()),
                    "paciente": paciente_sel,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                    "tipo": tipo_estudio,
                    "detalle": detalle_estudio,
                    "imagen": img_b64,
                    "extension": ext,
                    "firma": user.get("nombre", "Sistema"),
                })
                from core.database import _trim_db_list
                _trim_db_list("estudios_db", 200)
                
                # --- NUEVO CÓDIGO SQL Y STORAGE ---
                from core.database import supabase
                from core.db_sql import insert_estudio
                from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
                try:
                    partes = paciente_sel.split(" - ")
                    if len(partes) > 1 and supabase:
                        dni = partes[1].strip()
                        empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
                        empresa_id = _obtener_uuid_empresa(empresa)
                        if empresa_id:
                            pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                            if pac_uuid:
                                archivo_url = ""
                                if archivo_subido is not None or foto_estudio is not None:
                                    # Subir a Storage
                                    file_path = f"{pac_uuid}/{uuid4()}.{ext}"
                                    content_type = "application/pdf" if ext == "pdf" else f"image/{ext}"
                                    
                                    # Usamos los bytes originales o los optimizados
                                    bytes_a_subir = raw_bytes
                                    supabase.storage.from_("medicare-estudios").upload(file_path, bytes_a_subir, {"content-type": content_type})
                                    archivo_url = supabase.storage.from_("medicare-estudios").get_public_url(file_path)
                                    
                                datos_sql = {
                                    "paciente_id": pac_uuid,
                                    "medico_solicitante": user.get("nombre", "Sistema"),
                                    "tipo_estudio": tipo_estudio,
                                    "fecha_realizacion": ahora().date().isoformat(),
                                    "informe": detalle_estudio,
                                    "archivo_url": archivo_url,
                                    "estado": "Completado"
                                }
                                insert_estudio(datos_sql)
                except Exception as e:
                    from core.app_logging import log_event
                    log_event("estudios_sql", f"error_dual_write:{type(e).__name__}")
                # ----------------------------------
                
                guardar_datos(spinner=True)
                queue_toast("Estudio guardado correctamente.")
                st.rerun()
    else:
        st.caption("La carga de estudios queda deshabilitada para este rol.")

    # --- SWITCH FINAL: LECTURA DESDE POSTGRESQL ---
    from core.db_sql import get_estudios_by_paciente
    from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
    
    estudios_pac = []
    uso_sql = False
    
    try:
        partes = paciente_sel.split(" - ")
        if len(partes) > 1:
            dni = partes[1].strip()
            empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
            empresa_id = _obtener_uuid_empresa(empresa)
            
            if empresa_id:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                if pac_uuid:
                    estudios_sql = get_estudios_by_paciente(pac_uuid)
                    uso_sql = True
                    
                    for e in estudios_sql:
                        fecha_raw = e.get("fecha_realizacion", "")
                        fecha_fmt = ""
                        if fecha_raw:
                            d_parts = fecha_raw.split("-")
                            if len(d_parts) == 3:
                                fecha_fmt = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]} 00:00:00"
                        
                        estudios_pac.append({
                            "id_sql": e.get("id"),
                            "paciente": paciente_sel,
                            "fecha": fecha_fmt,
                            "tipo": e.get("tipo_estudio", ""),
                            "detalle": e.get("informe", ""),
                            "archivo_url": e.get("archivo_url", ""),
                            "firma": e.get("medico_solicitante", "Sistema"),
                            "extension": "pdf" if ".pdf" in str(e.get("archivo_url", "")).lower() else "jpg"
                        })
    except Exception as e:
        from core.app_logging import log_event
        log_event("estudios_sql", f"error_lectura:{type(e).__name__}")
        
    if not uso_sql:
        estudios_pac = [e for e in st.session_state.get("estudios_db", []) if e.get("paciente") == paciente_sel]
    # ----------------------------------------------

    if not estudios_pac:
        bloque_estado_vacio(
            "Sin estudios adjuntos",
            "Todavía no hay estudios guardados para este paciente.",
            sugerencia="Usá el formulario de carga superior si tu rol lo permite.",
        )
        return

    # ── Métricas + alertas de pendientes / críticos ───────────────────────────
    from datetime import datetime as _dt
    _CRITICOS = {"Tomografia (TAC)", "Resonancia Magnetica (RMN)", "Electrocardiograma (ECG)"}
    _SIN_RESULTADO = "Sin resultado"

    pendientes = [
        e for e in estudios_pac
        if str(e.get("detalle", "")).strip().lower() in ("", "sin resultado", "-", "s/d")
        or str(e.get("estado", "")).strip().lower() in ("pendiente", "solicitado", "")
    ]
    criticos_sin_respuesta = []
    hoy_dt = _dt.now()
    for e in pendientes:
        if e.get("tipo") in _CRITICOS:
            try:
                f_est = parse_fecha_hora(e.get("fecha", ""))
                if f_est and (hoy_dt.replace(tzinfo=None) - f_est).days > 7:
                    criticos_sin_respuesta.append(e)
            except Exception as _exc:
                from core.app_logging import log_event
                log_event("estudios_fecha_parse", f"fallo_parse_fecha_critica:{e.get('tipo','S/D')}:{e.get('fecha','')}:{type(_exc).__name__}")

    if criticos_sin_respuesta:
        st.error(
            f"🔴 {len(criticos_sin_respuesta)} estudio(s) crítico(s) sin resultado en más de 7 días: "
            + " | ".join(f"{e.get('tipo','S/D')} ({e.get('fecha','')[:10]})" for e in criticos_sin_respuesta[:3])
        )
    elif pendientes:
        st.warning(f"🟡 {len(pendientes)} estudio(s) sin resultado cargado.")

    _c1, _c2, _c3, _c4 = st.columns(4)
    _c1.metric("Total estudios", len(estudios_pac))
    _c2.metric("Sin resultado", len(pendientes))
    _c3.metric("Críticos >7d", len(criticos_sin_respuesta))
    _tipos_uniq = len({e.get("tipo", "") for e in estudios_pac if e.get("tipo")})
    _c4.metric("Tipos distintos", _tipos_uniq)

    st.divider()
    st.markdown("#### Archivo de Estudios del Paciente")

    if puede_borrar:
        col_del1, col_del1_chk = st.columns([3, 1.2])
        confirmar_ultimo = col_del1_chk.checkbox("Confirmar ultimo", key="conf_del_ultimo_estudio")
        if col_del1.button("Borrar ultimo estudio", use_container_width=True, disabled=not confirmar_ultimo):
            if not estudios_pac:
                st.error("No hay estudios para borrar.")
            else:
                ultimo_est = estudios_pac[-1]
                if not uso_sql:
                    try:
                        st.session_state["estudios_db"].remove(ultimo_est)
                    except ValueError:
                        pass  # Intencional: item ya fue removido por otra operación concurrente
                
                # --- ACTUALIZAR EN SQL ---
                if ultimo_est.get("id_sql"):
                    from core.db_sql import delete_estudio
                    delete_estudio(ultimo_est["id_sql"])
                # -------------------------
                
                guardar_datos(spinner=True)
                queue_toast("Estudio eliminado correctamente.")
                st.rerun()

        st.markdown("**Selecciona el estudio que quieres eliminar:**")
        opciones = []
        for est in reversed(estudios_pac[-200:]):
            label = f"{est['fecha']} - {est['tipo']}"
            if est.get("detalle"):
                label += f" | {est['detalle'][:50]}..."
            opciones.append((label, est))

        estudio_seleccionado = st.selectbox("Elegir estudio a borrar", options=opciones, format_func=lambda x: x[0], key="selector_borrar_estudio")
        col_sel_chk, col_sel_btn = st.columns([1.2, 2.8])
        confirmar_estudio = col_sel_chk.checkbox("Confirmar seleccion", key="conf_borrar_estudio")
        if col_sel_btn.button("Eliminar el estudio seleccionado", type="secondary", use_container_width=True, disabled=not confirmar_estudio):
            objetivo = estudio_seleccionado[1]
            st.session_state["estudios_db"] = [
                e for e in st.session_state.get("estudios_db", [])
                if not _mismo_estudio(e, objetivo)
            ]
            
            # --- ACTUALIZAR EN SQL ---
            if objetivo.get("id_sql"):
                from core.db_sql import delete_estudio
                delete_estudio(objetivo["id_sql"])
            # -------------------------
            
            guardar_datos(spinner=True)
            queue_toast("Estudio eliminado correctamente.")
            st.rerun()
    else:
        st.caption("La eliminacion de estudios queda reservada a medico, coordinacion o administracion total.")

    st.divider()

    # ── Filtros: tipo + búsqueda ───────────────────────────────────
    tipos_disponibles = sorted({e.get("tipo", "") for e in estudios_pac if e.get("tipo")})
    _fcol1, _fcol2 = st.columns([2, 3])
    filtro_tipo = _fcol1.selectbox(
        "Filtrar por tipo",
        ["Todos"] + tipos_disponibles,
        key="est_filtro_tipo",
    )
    busqueda_est = _fcol2.text_input(
        "🔍 Buscar en estudios",
        placeholder="Palabras clave en detalle, tipo o profesional...",
        key="est_busqueda",
    ).strip().lower()

    estudios_filtrados = estudios_pac
    if filtro_tipo != "Todos":
        estudios_filtrados = [e for e in estudios_filtrados if e.get("tipo") == filtro_tipo]
    if busqueda_est:
        estudios_filtrados = [
            e for e in estudios_filtrados
            if busqueda_est in str(e.get("detalle", "")).lower()
            or busqueda_est in str(e.get("tipo", "")).lower()
            or busqueda_est in str(e.get("firma", "")).lower()
            or busqueda_est in str(e.get("fecha", "")).lower()
        ]
        st.caption(f"{len(estudios_filtrados)} resultado(s) para '{busqueda_est}'")

    limite_est = seleccionar_limite_registros(
        "Mostrar ultimos estudios",
        len(estudios_filtrados),
        key="lim_estudios_tab",
        default=20,
    )
    estudios_mostrar = estudios_filtrados[-limite_est:]
    cargar_multimedia = st.checkbox("Cargar imagenes y PDF adjuntos", value=False, key="cargar_estudios_adjuntos")
    st.caption(f"Mostrando {len(estudios_mostrar)} de {len(estudios_filtrados)} estudios" + (f" (total: {len(estudios_pac)})" if len(estudios_filtrados) < len(estudios_pac) else "."))

    with lista_plegable("Archivo de estudios (detalle y adjuntos)", count=len(estudios_mostrar), expanded=False, height=520):
        for idx, est in enumerate(reversed(estudios_mostrar)):
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{est['fecha']}** | **{est['firma']}**")
                    st.markdown(f"**{est['tipo']}**")
                    if est.get("detalle"):
                        st.caption(est.get("detalle"))
                with col2:
                    if puede_borrar:
                        cf = st.checkbox(
                            "Confirmo eliminar",
                            key=f"cf_del_est_{est['fecha']}_{idx}",
                            help="Evita borrados accidentales en la lista.",
                        )
                        if st.button(
                            "Eliminar",
                            key=f"del_est_{est['fecha']}_{idx}",
                            disabled=not cf,
                            type="secondary",
                        ):
                            st.session_state["estudios_db"] = [
                                e for e in st.session_state["estudios_db"]
                                if not _mismo_estudio(e, est)
                            ]
                            guardar_datos(spinner=True)
                            st.rerun()

                if cargar_multimedia:
                    if est.get("archivo_url") and est["archivo_url"].startswith("http"):
                        # Es una URL de Supabase Storage
                        if est.get("extension") == "pdf" or ".pdf" in est["archivo_url"].lower():
                            st.link_button("Abrir PDF en el navegador", est["archivo_url"], use_container_width=True)
                        else:
                            st.image(est["archivo_url"], caption="Documento Adjunto", use_container_width=True)
                    elif est.get("imagen"):
                        # Es el base64 legacy
                        try:
                            img_bytes = base64.b64decode(est["imagen"])
                            if img_bytes.startswith(b"%PDF") or est.get("extension") == "pdf":
                                nombre_arch = f"Estudio_{est['fecha'][:10].replace('/', '-')}.pdf"
                                st.download_button("Descargar PDF", data=img_bytes, file_name=nombre_arch, mime="application/pdf", key=f"pdf_est_{est['fecha']}_{idx}", use_container_width=True)
                            else:
                                st.image(img_bytes, caption="Documento Adjunto", use_container_width=True)
                        except Exception:
                            st.error("Error al leer el archivo")

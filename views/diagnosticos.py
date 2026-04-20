"""
PANEL DE DIAGNOSTICO DEL SISTEMA
Vista exclusiva para superadmin: verifica Supabase, tablas SQL, datos locales, errores,
estado del sistema, logs, memoria y configuración.
"""
import streamlit as st
import time
from datetime import datetime
from pathlib import Path


def render_diagnosticos(user=None):
    st.markdown("# 🔍 Diagnóstico del Sistema")
    st.caption("Verificación técnica completa - Solo Super Administradores")

    # Solo superadmin puede acceder (control total)
    from core.utils import es_control_total
    rol = user.get("rol", "") if user else ""
    if not es_control_total(rol):
        st.error("🔒 Acceso restringido. Solo Super Administradores pueden acceder al diagnóstico completo.")
        return

    empresa_actual = ""
    if user:
        empresa_actual = user.get("empresa", "")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🗄️ Estado Supabase", 
        "🏢 Empresa / Pacientes", 
        "💾 Datos Locales",
        "🔧 Diagnóstico Técnico"
    ])

    # === TAB 1: ESTADO SUPABASE ===
    with tab1:
        st.markdown("### Estado de la Conexión y Tablas SQL")

        if st.button("🔄 Ejecutar Diagnóstico Completo", type="primary", use_container_width=True):
            with st.spinner("Diagnosticando Supabase..."):
                from core.diagnosticos import diagnosticar_supabase
                diag = diagnosticar_supabase()
                st.session_state["_ultimo_diagnostico"] = diag
                st.session_state["_ultimo_diagnostico_ts"] = time.time()

        diag = st.session_state.get("_ultimo_diagnostico")
        diag_ts = st.session_state.get("_ultimo_diagnostico_ts", 0)
        CACHE_EXPIRE_SEGUNDOS = 600  # 10 minutos de cache para diagnosticos
        
        if not diag or (time.time() - diag_ts) > CACHE_EXPIRE_SEGUNDOS:
            st.info("Presioná el botón para ejecutar el diagnóstico.")
            if diag and (time.time() - diag_ts) > CACHE_EXPIRE_SEGUNDOS:
                st.caption(f"Datos del diagnóstico expiraron (hace más de {CACHE_EXPIRE_SEGUNDOS//60} minutos).")
        else:
            ts = diag.get("timestamp", "")
            st.caption(f"Última verificación: {ts}")

            # Conexión
            if diag["conexion_ok"]:
                st.success("✅ Conexión a Supabase: OK")
            else:
                st.error(f"❌ Sin conexión a Supabase: {diag.get('error_conexion','Error desconocido')}")
                return

            # medicare_db
            mdb = diag.get("medicare_db_rows", 0)
            if isinstance(mdb, int) and mdb > 0:
                st.success(f"✅ Tabla `medicare_db` (JSON principal): **{mdb} filas**")
            else:
                st.warning(f"⚠️ Tabla `medicare_db`: {mdb} filas o error")

            # Empresas
            empresas = diag.get("empresas_registradas", [])
            if empresas and "error" not in str(empresas[0]):
                nombres = ", ".join(e.get("nombre","?") for e in empresas)
                st.success(f"✅ Empresas registradas ({len(empresas)}): **{nombres}**")
            else:
                st.error("❌ No hay empresas registradas en Supabase. Esto impide guardar pacientes en tablas SQL.")
                if empresa_actual:
                    if st.button(f"🔧 Insertar empresa '{empresa_actual}' automáticamente", type="primary"):
                        with st.spinner(f"Insertando '{empresa_actual}' en Supabase..."):
                            from core.diagnosticos import insertar_empresa_en_supabase
                            res = insertar_empresa_en_supabase(empresa_actual.strip())
                        if res["insertado"]:
                            st.success(f"✅ Empresa insertada correctamente: **{res['nombre_empresa']}** (ID: {res['empresa_id']})")
                            st.info("Recarga la página para ver los cambios reflejados.")
                        else:
                            st.error(f"❌ Error al insertar empresa: {res['error']}")

            # Tabla de estado de cada tabla
            st.markdown("#### Tablas SQL")
            tablas_data = diag.get("tablas", {})
            
            # Caché para dataframe de tablas (evita recrear en cada rerun si no cambió el diagnóstico)
            df_cache_key = "_mc_diag_df_tablas"
            diag_hash = hash(str(sorted(tablas_data.items())))
            cached_df = st.session_state.get(df_cache_key)
            
            if cached_df and cached_df.get("hash") == diag_hash:
                df_tablas = cached_df["df"]
            else:
                filas_estado = []
                for tabla, info in tablas_data.items():
                    if not info["existe"]:
                        estado = "❌ No existe"
                        color = "🔴"
                    elif not info["columnas_ok"]:
                        falt = ", ".join(info["columnas_faltantes"])
                        estado = f"⚠️ Faltan columnas: {falt}"
                        color = "🟡"
                    else:
                        estado = "✅ OK"
                        color = "🟢"
                    filas_estado.append({
                        "": color,
                        "Tabla": f"`{tabla}`",
                        "Existe": "Sí" if info["existe"] else "No",
                        "Filas": info.get("filas", 0),
                        "Estado": estado,
                        "Error": info.get("error") or ""
                    })
                
                import pandas as pd
                df_tablas = pd.DataFrame(filas_estado)
                st.session_state[df_cache_key] = {"hash": diag_hash, "df": df_tablas}
            
            st.dataframe(df_tablas, use_container_width=True, hide_index=True)

    # === TAB 2: EMPRESA / PACIENTES ===
    with tab2:
        st.markdown("### Verificar Empresa en Supabase")
        st.info(
            "Este es el punto de falla más común. Para guardar pacientes en las tablas SQL, "
            "la empresa debe existir en la tabla `empresas`. "
            "Si no existe, los pacientes solo se guardan en el blob JSON `medicare_db`."
        )

        empresa_check = st.text_input(
            "Nombre exacto de la empresa a verificar",
            value=empresa_actual,
            placeholder="Ej: Clinica General"
        )

        if st.button("🔍 Verificar Empresa", type="primary"):
            if empresa_check.strip():
                with st.spinner(f"Verificando '{empresa_check}'..."):
                    from core.diagnosticos import diagnosticar_empresa_en_supabase
                    res = diagnosticar_empresa_en_supabase(empresa_check.strip())

                if res["empresa_encontrada"]:
                    st.success(f"✅ Empresa encontrada: **{res['nombre_empresa']}**")
                    st.code(f"empresa_id = {res['empresa_id']}")
                    st.success("✅ Los pacientes SÍ pueden guardarse en las tablas SQL")
                else:
                    st.error(f"❌ {res['error']}")
                    st.markdown(
                        "**¿Qué significa esto?**\n"
                        "- Los datos de pacientes, evoluciones, etc. se guardan en `medicare_db` (JSON blob) ✅\n"
                        "- La sincronización a tablas SQL (`pacientes`, `evoluciones`, etc.) falla silenciosamente ⚠️\n"
                        "- Los datos NO se pierden, siguen en `medicare_db`\n\n"
                        "**Solución:** Insertar la empresa en la tabla `empresas` de Supabase con el nombre exacto que figura abajo."
                    )
                    st.code(f"INSERT INTO empresas (nombre) VALUES ('{empresa_check.strip()}');")
            else:
                st.warning("Ingresá el nombre de la empresa.")

        st.markdown("---")
        st.markdown("### Inspeccionar Schema de una Tabla")
        tabla_inspect = st.selectbox("Seleccionar tabla", ["pacientes", "evoluciones", "empresas", "signos_vitales", "indicaciones", "turnos", "medicare_db"])
        if st.button("🔎 Ver Columnas Reales", key="btn_schema"):
            from core.diagnosticos import obtener_schema_tabla
            schema = obtener_schema_tabla(tabla_inspect)
            if schema["error"]:
                st.error(f"Error: {schema['error']}")
            else:
                st.success(f"Columnas reales de `{tabla_inspect}`:")
                st.code(", ".join(schema["columnas"]))
                if schema.get("muestra"):
                    st.markdown("**Ejemplo de fila:**")
                    import json
                    st.json(schema["muestra"])

    # === TAB 3: DATOS LOCALES ===
    with tab3:
        st.markdown("### Estado del Archivo de Datos Local")
        from core.guardado_universal import _load_data

        data = _load_data()
        local_path = Path(".streamlit/local_data.json")

        if local_path.exists():
            size_kb = round(local_path.stat().st_size / 1024, 1)
            st.success(f"✅ Archivo local: `{local_path}` ({size_kb} KB)")
        else:
            st.warning("⚠️ Archivo local no encontrado.")

        # Conteos por tipo
        st.markdown("#### Registros en Archivo Local")
        import pandas as pd
        tipos = ["pacientes", "historial", "evoluciones", "signos_vitales", "materiales", "recetas", "visitas"]
        conteos = []
        for t in tipos:
            registros = data.get(t, [])
            pacientes_unicos = len(set(r.get("paciente_id","") for r in registros if r.get("paciente_id")))
            conteos.append({"Tipo": t, "Total registros": len(registros), "Pacientes únicos": pacientes_unicos})

        df_local = pd.DataFrame(conteos)
        st.dataframe(df_local, use_container_width=True, hide_index=True)

        # Conteos session_state
        st.markdown("#### Registros en Sesión Activa (RAM)")
        claves_ss = ["pacientes_db", "evoluciones_db", "vitales_db", "indicaciones_db",
                     "cuidados_enfermeria_db", "inventario_db", "facturacion_db"]
        ss_data = []
        for clave in claves_ss:
            val = st.session_state.get(clave, [])
            ss_data.append({"Clave": clave, "Items": len(val) if isinstance(val, list) else "dict"})
        df_ss = pd.DataFrame(ss_data)
        st.dataframe(df_ss, use_container_width=True, hide_index=True)

        # Backups
        st.markdown("#### Backups Disponibles")
        backup_files = sorted(Path(".streamlit").glob("backup_*.json"), reverse=True)[:10]
        if backup_files:
            for bf in backup_files:
                size = round(bf.stat().st_size / 1024, 1)
                st.caption(f"📦 `{bf.name}` — {size} KB")
        else:
            st.info("No hay backups disponibles.")

    # === TAB 4: DIAGNOSTICO TECNICO AVANZADO ===
    with tab4:
        st.markdown("### 🔧 Diagnóstico Técnico del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🖥️ Estado del Sistema")
            
            # Memoria RAM
            try:
                import psutil
                mem = psutil.virtual_memory()
                ram_used = mem.used / (1024**3)
                ram_total = mem.total / (1024**3)
                ram_percent = mem.percent
                
                if ram_percent > 90:
                    st.error(f"⚠️ RAM: {ram_percent}% ({ram_used:.1f}/{ram_total:.1f} GB) - CRÍTICO")
                elif ram_percent > 75:
                    st.warning(f"⚡ RAM: {ram_percent}% ({ram_used:.1f}/{ram_total:.1f} GB) - Alto")
                else:
                    st.success(f"✅ RAM: {ram_percent}% ({ram_used:.1f}/{ram_total:.1f} GB)")
            except ImportError:
                st.info("ℹ️ Instalar `psutil` para ver uso de RAM")
            
            # Disco
            try:
                import psutil
                disk = psutil.disk_usage('.')
                disk_percent = disk.percent
                if disk_percent > 90:
                    st.error(f"⚠️ Disco: {disk_percent}% usado - CRÍTICO")
                elif disk_percent > 80:
                    st.warning(f"⚡ Disco: {disk_percent}% usado - Alto")
                else:
                    st.success(f"✅ Disco: {disk_percent}% usado")
            except Exception:
                pass
            
            # Python version
            import sys
            st.caption(f"Python: {sys.version.split()[0]}")
            
            # Streamlit version
            try:
                import streamlit as st_mod
                st.caption(f"Streamlit: {st_mod.__version__}")
            except Exception:
                pass
        
        with col2:
            st.markdown("#### 🔐 Variables de Entorno")
            
            # Verificar secrets/configuración
            required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
            secrets_ok = True
            
            for var in required_vars:
                try:
                    val = st.secrets.get(var, "")
                    if val:
                        masked = val[:10] + "..." + val[-4:] if len(val) > 20 else "***"
                        st.success(f"✅ {var}: {masked}")
                    else:
                        st.error(f"❌ {var}: NO CONFIGURADO")
                        secrets_ok = False
                except Exception as e:
                    st.error(f"❌ {var}: Error - {str(e)[:50]}")
                    secrets_ok = False
            
            if not secrets_ok:
                st.warning("⚠️ Algunas variables de entorno no están configuradas correctamente")
        
        st.markdown("---")
        
        # Logs de errores recientes
        st.markdown("#### 📋 Logs de Errores Recientes")
        
        try:
            from core.app_logging import get_recent_errors
            errores = get_recent_errors(limit=20)
            
            if errores:
                st.error(f"⚠️ {len(errores)} errores recientes detectados")
                
                with st.expander("Ver errores recientes", expanded=False):
                    for err in errores:
                        ts = err.get("timestamp", "?")
                        msg = err.get("message", "Sin mensaje")
                        st.markdown(f"**{ts}**: `{msg[:150]}{'...' if len(msg) > 150 else ''}`")
            else:
                st.success("✅ No hay errores recientes en el log")
        except Exception as e:
            st.info(f"ℹ️ Sistema de logs en memoria no disponible: {e}")
        
        st.markdown("---")
        
        # Verificación de archivos críticos
        st.markdown("#### 📁 Verificación de Archivos Críticos")
        
        archivos_criticos = [
            ("main.py", "Archivo principal"),
            ("core/database.py", "Base de datos"),
            ("core/utils.py", "Utilidades"),
            ("assets/style.css", "Estilos CSS"),
            ("requirements.txt", "Dependencias"),
        ]
        
        cols = st.columns(3)
        for i, (archivo, desc) in enumerate(archivos_criticos):
            path = Path(archivo)
            with cols[i % 3]:
                if path.exists():
                    size = path.stat().st_size
                    st.success(f"✅ {desc}")
                    st.caption(f"{size/1024:.1f} KB")
                else:
                    st.error(f"❌ {desc}")
                    st.caption(f"Archivo no encontrado: {archivo}")
        
        st.markdown("---")
        
        # Botón de diagnóstico completo
        if st.button("🔄 Ejecutar Diagnóstico Completo del Sistema", type="primary", use_container_width=True):
            with st.spinner("Analizando todo el sistema..."):
                progress = st.progress(0)
                
                # Simular pasos de diagnóstico
                time.sleep(0.5)
                progress.progress(25)
                
                # Verificar dependencias (usa nombres de import, no de pip)
                dependencias_faltantes = []
                # Mapa: (nombre_pip, nombre_import)
                deps = [
                    ("streamlit", "streamlit"),
                    ("pandas", "pandas"),
                    ("requests", "requests"),
                    ("pillow", "PIL"),
                    ("psutil", "psutil"),
                ]
                for pip_name, import_name in deps:
                    try:
                        __import__(import_name)
                    except ImportError:
                        dependencias_faltantes.append(pip_name)
                
                time.sleep(0.5)
                progress.progress(50)
                
                # Verificar conexiones
                errores_conexion = []
                try:
                    from core.database import supabase
                    if not supabase:
                        errores_conexion.append("Supabase no inicializado")
                except Exception as e:
                    errores_conexion.append(f"Error Supabase: {str(e)[:50]}")
                
                time.sleep(0.5)
                progress.progress(75)
                
                # Verificar session state
                problemas_session = []
                required_keys = ["pacientes_db", "evoluciones_db", "vitales_db"]
                for key in required_keys:
                    if key not in st.session_state:
                        problemas_session.append(f"Falta: {key}")
                
                time.sleep(0.3)
                progress.progress(100)
                
                # Mostrar resultados
                st.markdown("#### 📊 Resultados del Diagnóstico")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if dependencias_faltantes:
                        st.error(f"❌ {len(dependencias_faltantes)} dependencias faltantes")
                        st.code(", ".join(dependencias_faltantes))
                    else:
                        st.success("✅ Todas las dependencias OK")
                
                with col2:
                    if errores_conexion:
                        st.error(f"❌ {len(errores_conexion)} problemas de conexión")
                        for e in errores_conexion:
                            st.caption(e)
                    else:
                        st.success("✅ Conexiones OK")
                
                with col3:
                    if problemas_session:
                        st.warning(f"⚠️ {len(problemas_session)} claves de sesión faltantes")
                        for p in problemas_session:
                            st.caption(p)
                    else:
                        st.success("✅ Session State OK")
                
                # Resumen final
                total_problemas = len(dependencias_faltantes) + len(errores_conexion) + len(problemas_session)
                
                if total_problemas == 0:
                    st.balloons()
                    st.success("🎉 Sistema completamente saludable. No se detectaron problemas.")
                else:
                    st.error(f"⚠️ Se detectaron {total_problemas} problemas que requieren atención")

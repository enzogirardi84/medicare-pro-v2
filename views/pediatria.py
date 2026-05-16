from core.alert_toasts import queue_toast
from datetime import datetime

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.db_sql import get_pediatria_by_paciente, insert_pediatria
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
from core.app_logging import log_event


def _parse_fecha_hora(fecha_str):
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(str(fecha_str or "").strip(), formato)
        except Exception:
            continue
    return datetime.min


def _resolver_uuid_paciente_sql(paciente_sel, empresa):
    partes = str(paciente_sel or "").rsplit(" - ", 1)
    dni = partes[1].strip() if len(partes) == 2 else ""
    empresa_id = _obtener_uuid_empresa(empresa) if empresa else None
    return _obtener_uuid_paciente(dni, empresa_id) if dni and empresa_id else None


def render_pediatria(paciente_sel, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Percentilo</h2>
            <p class="mc-hero-text">Peso, talla, IMC y percentiles con graficos de tendencia.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Curvas</span>
                <span class="mc-chip">Percentiles</span>
                <span class="mc-chip">Historial</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Curvas", "Peso, talla e IMC con tendencia en el tiempo."),
            ("Percentiles", "Se calculan con sexo y fecha de nacimiento del legajo."),
            ("Historial", "Cada control queda disponible para revision."),
        ]
    )
    st.caption(
        "Los percentiles aproximados usan sexo y fecha de nacimiento del legajo en **Admision**. Si no hay controles previos, el resumen aparece despues del primer guardado; el formulario de nuevo control esta mas abajo."
    )
    det = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    empresa_actual = str(
        det.get("empresa")
        or st.session_state.get("u_actual", {}).get("empresa")
        or st.session_state.get("user", {}).get("empresa")
        or ""
    ).strip()
    se = det.get("sexo", "F")
    f_n_str = det.get("fnac", "01/01/2000")
    f_n = pd.to_datetime(f_n_str, format="%d/%m/%Y", errors="coerce")
    if pd.isna(f_n):
        f_n = datetime(2000, 1, 1)

    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    ped = []
    try:
        paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
        if paciente_uuid:
            ped_sql = get_pediatria_by_paciente(paciente_uuid)
            if ped_sql:
                for p in ped_sql:
                    dt = pd.to_datetime(p.get("fecha_registro", ""), errors="coerce")
                    
                    # Calcular edad en meses y IMC para mostrar
                    edad_meses = 0.0
                    if pd.notnull(dt) and pd.notnull(f_n):
                        edad_meses = round((dt.tz_localize(None) - f_n).days / 30.4375, 1)
                        if edad_meses < 0: edad_meses = 0.0
                        
                    peso = float(p.get("peso_kg") or 0)
                    talla = float(p.get("talla_cm") or 0)
                    imc = round(peso / ((talla / 100) ** 2), 2) if talla > 0 else 0.0
                    
                    ped.append({
                        "paciente": paciente_sel,
                        "fecha": dt.strftime("%d/%m/%Y %H:%M") if pd.notnull(dt) else p.get("fecha_registro", ""),
                        "edad_meses": edad_meses,
                        "peso": peso,
                        "talla": talla,
                        "pc": float(p.get("perimetro_cefalico_cm") or 0),
                        "imc": imc,
                        "percentil_sug": p.get("percentilo_peso", ""),
                        "nota": p.get("observaciones", ""),
                        "firma": p.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(p.get("usuarios"), dict) else "Desconocido",
                        "id_sql": p.get("id")
                    })
    except Exception as e:
        log_event("error_leer_pediatria_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not ped:
        ped = [x for x in st.session_state.get("pediatria_db", []) if x.get("paciente") == paciente_sel]

    if ped:
        ped_ord = sorted(ped, key=lambda x: _parse_fecha_hora(x.get("fecha", "")))
        ultimo_ped = ped_ord[-1]
        penultimo_ped = ped_ord[-2] if len(ped_ord) >= 2 else None

        st.markdown("##### Resumen Actual")
        c1, c2, c3, c4 = st.columns(4)
        _delta_peso = round(float(ultimo_ped.get('peso', 0) or 0) - float(penultimo_ped.get('peso', 0) or 0), 2) if penultimo_ped else None
        _delta_talla = round(float(ultimo_ped.get('talla', 0) or 0) - float(penultimo_ped.get('talla', 0) or 0), 1) if penultimo_ped else None
        c1.metric("Peso", f"{ultimo_ped.get('peso', '-')} kg", delta=f"{_delta_peso:+.2f} kg" if _delta_peso is not None else None)
        c2.metric("Talla", f"{ultimo_ped.get('talla', '-')} cm", delta=f"{_delta_talla:+.1f} cm" if _delta_talla is not None else None)
        c3.metric("IMC", f"{ultimo_ped.get('imc', '-')}")
        c4.metric("Percentil", ultimo_ped.get("percentil_sug", "-"))

        # ── Alertas de percentil ─────────────────────────────────────────
        _PERC_CRITICO = {"P3 - Bajo peso"}
        _PERC_ALERTA = {"P97 - Sobrepeso"}
        _perc_actual = str(ultimo_ped.get("percentil_sug", "") or "")
        if _perc_actual in _PERC_CRITICO:
            st.error(f"🔴 Percentil crítico: **{_perc_actual}** — IMC {ultimo_ped.get('imc', '-')}. Evaluar nutrición y seguimiento.")
        elif _perc_actual in _PERC_ALERTA:
            st.warning(f"🟡 Percentil elevado: **{_perc_actual}** — IMC {ultimo_ped.get('imc', '-')}. Considerar derivación nutricional.")
        if penultimo_ped:
            _perc_prev = str(penultimo_ped.get("percentil_sug", "") or "")
            _orden = ["P3 - Bajo peso", "P50 - Normal", "P97 - Sobrepeso"]
            if _perc_actual in _orden and _perc_prev in _orden:
                if _orden.index(_perc_actual) < _orden.index(_perc_prev):
                    st.warning(f"🟡 Tendencia de peso en descenso: {_perc_prev} → {_perc_actual}. Verificar evolución.")
                elif _orden.index(_perc_actual) > _orden.index(_perc_prev):
                    st.warning(f"🟡 Tendencia de peso en aumento: {_perc_prev} → {_perc_actual}. Verificar evolución.")

        df_preview = pd.DataFrame(ped_ord)
        df_preview["fecha_dt"] = df_preview["fecha"].apply(_parse_fecha_hora)
        df_preview = df_preview.sort_values(by="fecha_dt")
        if len(df_preview) >= 2:
            st.markdown("##### Tendencia de crecimiento")
            col_graph1, col_graph2 = st.columns(2)
            with col_graph1:
                st.caption("Peso en el tiempo")
                st.line_chart(
                    df_preview.set_index("fecha")["peso"],
                    width='stretch',
                    color="#38bdf8",
                )
            with col_graph2:
                st.caption("Talla en el tiempo")
                st.line_chart(
                    df_preview.set_index("fecha")["talla"],
                    width='stretch',
                    color="#818cf8",
                )
            if df_preview["pc"].astype(float).gt(0).sum() >= 2:
                st.caption("Perímetro cefálico (cm)")
                st.line_chart(
                    df_preview.set_index("fecha")["pc"],
                    width='stretch',
                    color="#f59e0b",
                    height=140,
                )
            st.caption("Vista rapida para ver si el crecimiento viene acompanando la evolucion esperada.")

    st.divider()
    with st.form("pedia", clear_on_submit=True):
        st.markdown("##### Nuevo Control")
        tipo_ctrl = st.radio("Tipo de control", ["Menor", "Adulto"], horizontal=True, key="tipo_ctrl_ped")
        col_time1, col_time2 = st.columns(2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_ped")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_ped")
        col_a, col_b = st.columns(2)
        pes = col_a.number_input("Peso Actual (kg)", min_value=0.0, format="%.2f")
        tal = col_b.number_input("Talla Actual (cm)", min_value=0.0, format="%.2f")
        pc = col_a.number_input("Perimetro Cefalico (cm, solo percentilo)", min_value=0.0, format="%.2f")
        desc = col_b.text_input("Descripcion / Nota (opcional)")
        if st.form_submit_button("Guardar Control", width='stretch', type="primary"):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str_toma = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            dt_toma = _parse_fecha_hora(fecha_str_toma)
            eda_meses = round((dt_toma - f_n).days / 30.4375, 1) if f_n else 0.0
            if eda_meses < 0:
                eda_meses = 0.0
            imc = round(pes / ((tal / 100) ** 2), 2) if tal > 0 else 0.0
            es_adulto = tipo_ctrl == "Adulto"
            if es_adulto:
                percentil_sug = "Bajo peso" if imc < 18.5 else "Normal" if imc < 25 else "Sobrepeso" if imc < 30 else "Obesidad"
            elif se == "F":
                percentil_sug = "P3 - Bajo peso" if imc < 14 else "P50 - Normal" if imc < 18 else "P97 - Sobrepeso"
            else:
                percentil_sug = "P3 - Bajo peso" if imc < 14.5 else "P50 - Normal" if imc < 18.5 else "P97 - Sobrepeso"

            # 1. Guardar en SQL (Dual-Write)
            try:
                paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
                if paciente_uuid:
                    datos_sql = {
                        "paciente_id": paciente_uuid,
                        "fecha_registro": dt_toma.isoformat() if dt_toma else None,
                        "peso_kg": pes,
                        "talla_cm": tal,
                        "perimetro_cefalico_cm": pc,
                        "percentilo_peso": percentil_sug,
                        "percentilo_talla": "",
                        "observaciones": desc,
                        "tipo_control": "adulto" if es_adulto else "pediatrico",
                    }
                    insert_pediatria(datos_sql)
                    log_event("pediatria_sql_insert", f"Paciente: {paciente_uuid}")
            except Exception as e:
                log_event("error_pediatria_sql", str(e))

            # 2. Guardar en JSON (Legacy)
            if "pediatria_db" not in st.session_state:
                st.session_state["pediatria_db"] = []
            st.session_state["pediatria_db"].append({
                "paciente": paciente_sel,
                "fecha": fecha_str_toma,
                "edad_meses": eda_meses,
                "peso": pes,
                "talla": tal,
                "pc": pc,
                "imc": imc,
                "percentil_sug": percentil_sug,
                "nota": desc,
                "firma": user.get("nombre", "Sistema"),
                "tipo_control": "adulto" if es_adulto else "pediatrico",
            })
            from core.database import _trim_db_list
            _trim_db_list("pediatria_db", 500)
            guardar_datos(spinner=True)
            queue_toast("Guardado correctamente.")
            st.rerun()

    if ped:
        st.divider()
        if st.checkbox("Mostrar curvas de crecimiento", value=False):
            df_g = pd.DataFrame(ped)
            df_g["fecha_dt"] = df_g["fecha"].apply(_parse_fecha_hora)
            df_g = df_g.sort_values(by="fecha_dt")
            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                st.caption("Peso (kg)")
                st.line_chart(df_g.set_index("fecha")["peso"], width='stretch', color="#38bdf8")
            with col_g2:
                st.caption("Talla (cm)")
                st.line_chart(df_g.set_index("fecha")["talla"], width='stretch', color="#818cf8")
            with col_g3:
                st.caption("IMC")
                st.area_chart(df_g.set_index("fecha")["imc"], width='stretch', color="#22c55e")
        st.divider()
        col_tit, col_chk, col_btn = st.columns([3, 1.2, 1])
        col_tit.markdown("#### Historial")
        confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_ped")
        if col_btn.button("Borrar ultimo", width='stretch', disabled=not confirmar_borrado):
            if not ped:
                st.error("No hay registros para borrar.")
            else:
                try:
                    st.session_state["pediatria_db"].remove(ped[-1])
                except ValueError:
                    pass  # Intencional: item ya fue removido por otra operación concurrente
                guardar_datos(spinner=True)
                st.rerun()

        busqueda_ped = st.text_input(
            "🔍 Buscar en historial percentilo",
            placeholder="Percentil, nota, profesional o fecha...",
            key="ped_busqueda",
        ).strip().lower()
        ped_filtrado = ped
        if busqueda_ped:
            ped_filtrado = [
                p for p in ped
                if busqueda_ped in str(p.get("percentil_sug", "")).lower()
                or busqueda_ped in str(p.get("nota", "")).lower()
                or busqueda_ped in str(p.get("firma", "")).lower()
                or busqueda_ped in str(p.get("fecha", "")).lower()
            ]
            st.caption(f"{len(ped_filtrado)} resultado(s) para '{busqueda_ped}'")

        max_controles = min(200, len(ped_filtrado))
        if max_controles <= 10:
            limite = max_controles
            st.caption(f"Mostrando {limite} control(es) percentilo.")
        else:
            limite = st.slider("Controles percentilo a mostrar", min_value=10, max_value=max_controles, value=min(50, len(ped_filtrado)), step=10)
        df_ped = pd.DataFrame(ped_filtrado[-limite:]).drop(columns=["paciente"], errors='ignore')
        df_ped["fecha_dt"] = df_ped["fecha"].apply(_parse_fecha_hora)
        df_ped = df_ped.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
        with lista_plegable("Controles percentilo (tabla)", count=len(df_ped), expanded=False, height=400):
            mostrar_dataframe_con_scroll(df_ped, height=340)

from core.alert_toasts import queue_toast
from datetime import datetime

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll, seleccionar_limite_registros

# NUEVO: Sistema de guardado en Supabase (no ocupa RAM)
from core.supabase_storage import guardar_signos_vitales_seguro, obtener_signos_vitales_paciente


_RANGOS_VIT = {
    "FC":   {"min": 60,   "max": 100,  "crit_min": 40,   "crit_max": 130,  "unidad": "lpm"},
    "FR":   {"min": 12,   "max": 20,   "crit_min": 8,    "crit_max": 30,   "unidad": "rpm"},
    "Sat":  {"min": 94,   "max": 100,  "crit_min": 88,   "crit_max": 100,  "unidad": "%"},
    "Temp": {"min": 36.0, "max": 37.5, "crit_min": 35.0, "crit_max": 39.0, "unidad": "°C"},
    "HGT":  {"min": 70,   "max": 180,  "crit_min": 50,   "crit_max": 300,  "unidad": "mg/dL"},
}


def _evaluar_vit(clave, valor):
    r = _RANGOS_VIT.get(clave)
    if r is None:
        return None
    try:
        v = float(str(valor).replace(",", "."))
    except Exception:
        return None
    if v < r["crit_min"] or v > r["crit_max"]:
        return "critico"
    if v < r["min"] or v > r["max"]:
        return "alerta"
    return "normal"


def _evaluar_ta_clinica(ta_str):
    try:
        partes = str(ta_str or "").replace("/", " ").split()
        if len(partes) < 2:
            return None
        sis, dia = float(partes[0]), float(partes[1])
        if sis < 80 or sis > 180 or dia < 50 or dia > 120:
            return "critico"
        if sis < 90 or sis > 140 or dia < 60 or dia > 90:
            return "alerta"
        return "normal"
    except Exception:
        return None


def _mostrar_alertas_vitales_preview(ta, fc, fr, sat, temp, hgt):
    """Muestra alertas de rango DENTRO del formulario (antes de guardar)."""
    alertas_crit = []
    alertas_warn = []

    ta_est = _evaluar_ta_clinica(ta)
    if ta_est == "critico":
        alertas_crit.append(f"TA {ta} — valor crítico")
    elif ta_est == "alerta":
        alertas_warn.append(f"TA {ta} — fuera de rango normal (90-140/60-90 mmHg)")

    for clave, val in [("FC", fc), ("FR", fr), ("Sat", sat), ("Temp", temp), ("HGT", hgt)]:
        if val is None:
            continue
        est = _evaluar_vit(clave, val)
        r = _RANGOS_VIT[clave]
        if est == "critico":
            alertas_crit.append(f"{clave} = {val} {r['unidad']} — valor crítico (rango: {r['crit_min']}–{r['crit_max']})")
        elif est == "alerta":
            alertas_warn.append(f"{clave} = {val} {r['unidad']} — fuera de rango normal ({r['min']}–{r['max']})")

    for msg in alertas_crit:
        st.error(f"🔴 CRÍTICO: {msg}")
    for msg in alertas_warn:
        st.warning(f"🟡 Alerta: {msg}")
    return bool(alertas_crit), bool(alertas_warn)


def _parse_fecha_hora(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        except Exception:
            return datetime.min


def _edad_desde_fnac(fnac_str):
    if not fnac_str:
        return None
    try:
        fnac = datetime.strptime(str(fnac_str).strip(), "%d/%m/%Y").date()
        hoy = ahora().date()
        años = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))
        return años if años >= 0 else None
    except Exception:
        return None


def render_clinica(paciente_sel, user=None):
    from core.ui_liviano import headers_sugieren_equipo_liviano

    if not paciente_sel:
        aviso_sin_paciente()
        return

    user = user or {}
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    det = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    nombre_corto = paciente_sel.split(" (")[0]
    edad = _edad_desde_fnac(det.get("fnac", ""))

    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Clinica — Signos vitales</h2>
            <p class="mc-hero-text">Control clinico del paciente, alertas automaticas y evolucion en el tiempo. Pensado para uso rapido en domicilio o guardia.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Ultimo control</span>
                <span class="mc-chip">Tendencias</span>
                <span class="mc-chip">Alertas TA / FC / Sat / Temp</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Signos vitales", "Registra TA, FC, FR, saturacion, temperatura y HGT en cada visita."),
            ("Alertas", "Los valores fuera de rango se resaltan para actuar rapido."),
            ("Historial", "El grafico muestra la tendencia de FC en los ultimos controles."),
        ]
    )
    st.caption(
        "Abajo cargas un nuevo control; mas abajo el historial y el grafico. Las alertas se muestran al instante si TA, FC, saturacion o temperatura salen de rango."
    )

    if es_movil:
        c_inf1, c_inf2 = st.columns(2)
        c_inf1.metric("Paciente", nombre_corto[:24] + ("..." if len(nombre_corto) > 24 else ""))
        c_inf2.metric("Edad", f"{edad} años" if edad is not None else "S/D")
        st.metric("Obra social", (det.get("obra_social") or "S/D")[:28] or "S/D")
    else:
        c_inf1, c_inf2, c_inf3 = st.columns(3)
        c_inf1.metric("Paciente", nombre_corto[:28] + ("..." if len(nombre_corto) > 28 else ""))
        c_inf2.metric("Edad", f"{edad} años" if edad is not None else "S/D")
        c_inf3.metric("Obra social", (det.get("obra_social") or "S/D")[:24] or "S/D")

    alergias = str(det.get("alergias", "")).strip()
    if alergias:
        st.error(f"Alergias registradas: {alergias}")

    vits = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]

    if vits:
        vits_ordenados = sorted(vits, key=lambda x: _parse_fecha_hora(x.get("fecha", "")))
        ultimo = vits_ordenados[-1]

        # ── Semáforo del último control ─────────────────────────────────
        _estados_ult = {
            "TA": _evaluar_ta_clinica(ultimo.get("TA", "")),
            "FC": _evaluar_vit("FC", ultimo.get("FC")),
            "Sat": _evaluar_vit("Sat", ultimo.get("Sat")),
            "Temp": _evaluar_vit("Temp", ultimo.get("Temp")),
        }
        _hay_crit_ult = any(v == "critico" for v in _estados_ult.values())
        _hay_alert_ult = any(v == "alerta" for v in _estados_ult.values())
        _semaforo = "🔴 CRÍTICO" if _hay_crit_ult else ("🟡 Alerta" if _hay_alert_ult else "🟢 Normal")
        st.markdown(f"##### Último control registrado — {ultimo.get('fecha', 'S/D')[:16]}  **{_semaforo}**")
        if _hay_crit_ult or _hay_alert_ult:
            _msgs = [
                f"{k}={ultimo.get(k, '-')}" for k, est in _estados_ult.items()
                if est in ("critico", "alerta")
            ]
            if _hay_crit_ult:
                st.error(f"🔴 Valores críticos en último control: {' | '.join(_msgs)}")
            else:
                st.warning(f"🟡 Valores fuera de rango en último control: {' | '.join(_msgs)}")

        if es_movil:
            c1, c2 = st.columns(2)
            c1.metric("T.A.", ultimo.get("TA", "-"))
            c2.metric("F.C.", f"{ultimo.get('FC', '-')} lpm")
            c3, c4 = st.columns(2)
            c3.metric("F.R.", f"{ultimo.get('FR', '-')} rpm")
            c4.metric("SatO2", f"{ultimo.get('Sat', '-')} %")
            c5, c6 = st.columns(2)
            c5.metric("Temp", f"{ultimo.get('Temp', '-')} C")
            c6.metric("HGT", ultimo.get("HGT", "-"))
        else:
            r1, r2, r3 = st.columns(3)
            with r1:
                c1, c2 = st.columns(2)
                c1.metric("T.A.", ultimo.get("TA", "-"))
                c2.metric("F.C.", f"{ultimo.get('FC', '-')} lpm")
            with r2:
                c3, c4 = st.columns(2)
                c3.metric("F.R.", f"{ultimo.get('FR', '-')} rpm")
                c4.metric("SatO2", f"{ultimo.get('Sat', '-')} %")
            with r3:
                c5, c6 = st.columns(2)
                c5.metric("Temp", f"{ultimo.get('Temp', '-')} C")
                c6.metric("HGT", ultimo.get("HGT", "-"))

        if len(vits_ordenados) >= 2:
            try:
                penultimo = vits_ordenados[-2]
                delta_fc = int(ultimo.get("FC", 0)) - int(penultimo.get("FC", 0))
                try:
                    delta_sat = float(ultimo.get("Sat", 0)) - float(penultimo.get("Sat", 0))
                    _sat_txt = f" | SatO2 {'\u2191' if delta_sat > 0 else '\u2193' if delta_sat < 0 else '\u2192'}{abs(delta_sat):.0f}%"
                except Exception:
                    _sat_txt = ""
                try:
                    delta_ta = float(ultimo.get("TA", 0).split("/")[0]) - float(penultimo.get("TA", 0).split("/")[0])
                    _ta_txt = f" | TA {'\u2191' if delta_ta > 0 else '\u2193' if delta_ta < 0 else '\u2192'}{abs(delta_ta):.0f} mmHg"
                except Exception:
                    _ta_txt = ""
                st.caption(
                    f"Tendencia vs control previo — FC: {'\u2191' if delta_fc > 0 else '\u2193' if delta_fc < 0 else '\u2192'}{abs(delta_fc)} lpm"
                    + _sat_txt
                    + _ta_txt
                )
            except Exception as e:
                from core.app_logging import log_event
                log_event('clinica_error', f'Error: {e}')

        if len(vits_ordenados) >= 3:
            st.markdown("##### Tendencia de signos vitales")
            df_trend = pd.DataFrame(vits_ordenados[-20:])
            df_trend["_t"] = df_trend["fecha"].apply(_parse_fecha_hora)
            df_trend = df_trend[df_trend["_t"] != datetime.min]
            if len(df_trend) >= 2:
                # Extraer TA sistólica numérica
                def _ta_sis(ta_str):
                    try:
                        return float(str(ta_str or "").replace("/", " ").split()[0])
                    except Exception:
                        return None
                df_trend["TA_sis"] = df_trend["TA"].apply(_ta_sis)
                df_trend["FC"] = pd.to_numeric(df_trend["FC"], errors="coerce")
                df_trend["Sat"] = pd.to_numeric(df_trend["Sat"], errors="coerce")
                df_trend["Temp"] = pd.to_numeric(df_trend["Temp"], errors="coerce")
                _tr = df_trend.set_index("_t")
                _ch1, _ch2 = st.columns(2)
                if _tr["FC"].notna().sum() >= 2:
                    _ch1.caption("F.C. (lpm)")
                    _ch1.line_chart(_tr[["FC"]].rename(columns={"FC": "F.C."}), use_container_width=True, height=140)
                if _tr["Sat"].notna().sum() >= 2:
                    _ch2.caption("SatO2 (%)")
                    _ch2.line_chart(_tr[["Sat"]].rename(columns={"Sat": "SatO2"}), use_container_width=True, height=140)
                _ch3, _ch4 = st.columns(2)
                if _tr["TA_sis"].notna().sum() >= 2:
                    _ch3.caption("TA sistólica (mmHg)")
                    _ch3.line_chart(_tr[["TA_sis"]].rename(columns={"TA_sis": "TA sis."}), use_container_width=True, height=140)
                if _tr["Temp"].notna().sum() >= 2:
                    _ch4.caption("Temperatura (°C)")
                    _ch4.line_chart(_tr[["Temp"]].rename(columns={"Temp": "Temp °C"}), use_container_width=True, height=140)
    else:
        bloque_estado_vacio(
            "Sin signos vitales",
            "Todavía no hay controles de signos vitales para este paciente.",
            sugerencia="Completá el formulario superior y guardá para ver el historial acá.",
        )

    st.divider()
    with st.form("vitales_f", clear_on_submit=True):
        st.markdown("##### Nuevo control de signos vitales")
        col_time1, col_time2 = st.columns([1.15, 0.85] if es_movil else 2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_vits")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_vits")
        ta = st.text_input(
            "Tension arterial (TA)",
            "120/80",
            help="Normal: 90-140 / 60-90 mmHg",
        )
        if es_movil:
            r_s1, r_s2 = st.columns(2)
            fc = r_s1.number_input("F.C. (lpm)", 30, 220, 75, help="Normal: 60-100 lpm")
            fr = r_s2.number_input("F.R. (rpm)", 8, 60, 16, help="Normal: 12-20 rpm")
            r_s3, r_s4 = st.columns(2)
            sat = r_s3.number_input("SatO2 (%)", 70, 100, 96, help="Normal: ≥94%")
            temp = r_s4.number_input("Temperatura (C)", 34.0, 42.0, 36.5, step=0.1, help="Normal: 36-37.5°C")
            hgt = st.text_input("HGT (mg/dL)", "110", help="Normal: 70-180 mg/dL")
        else:
            r_s1, r_s2, r_s3 = st.columns(3)
            fc = r_s1.number_input("F.C. (lpm)", 30, 220, 75, help="Normal: 60-100 lpm")
            fr = r_s2.number_input("F.R. (rpm)", 8, 60, 16, help="Normal: 12-20 rpm")
            sat = r_s3.number_input("SatO2 (%)", 70, 100, 96, help="Normal: ≥94%")
            r_s4, r_s5 = st.columns(2)
            temp = r_s4.number_input("Temperatura (C)", 34.0, 42.0, 36.5, step=0.1, help="Normal: 36-37.5°C")
            hgt = r_s5.text_input("HGT (mg/dL)", "110", help="Normal: 70-180 mg/dL")
        obs = st.text_input("Observaciones (opcional)", "", placeholder="Ej.: paciente en ayunas, edema MMII...")

        hay_critico, hay_alerta = _mostrar_alertas_vitales_preview(ta, fc, fr, sat, temp, hgt)

        label_btn = "⚠️ Guardar (hay alertas)" if (hay_critico or hay_alerta) else "Guardar signos vitales"
        btn_type = "secondary" if hay_critico else "primary"
        if st.form_submit_button(label_btn, use_container_width=True, type=btn_type):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            registro = {
                "paciente": paciente_sel,
                "TA": ta,
                "FC": fc,
                "FR": fr,
                "Sat": sat,
                "Temp": temp,
                "HGT": hgt,
                "fecha": fecha_str,
            }
            if obs.strip():
                registro["observaciones"] = obs.strip()
            if user.get("nombre"):
                registro["registrado_por"] = user.get("nombre", "")
            st.session_state.setdefault("vitales_db", [])
            st.session_state["vitales_db"].append(registro)
            guardar_datos(spinner=True)
            st.session_state.pop(f"_ce_secs_{paciente_sel}", None)
            st.session_state.pop(f"_ce_ctx_{paciente_sel}", None)
            if hay_critico:
                queue_toast("⚠️ Signos vitales guardados — revisar valores CRÍTICOS.")
            elif hay_alerta:
                queue_toast("Signos vitales guardados — algunos valores fuera de rango.")
            else:
                queue_toast("Signos vitales guardados correctamente.")
            st.rerun()

    if vits:
        st.divider()
        col_tit, col_chk, col_btn = st.columns([3, 1.2, 1])
        col_tit.markdown("#### Historial de signos vitales")
        confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_borrar_vital")
        if col_btn.button("Borrar ultimo control", use_container_width=True, disabled=not confirmar_borrado):
            try:
                st.session_state["vitales_db"].remove(vits[-1])
            except ValueError:
                pass
            guardar_datos(spinner=True)
            queue_toast("Registro eliminado.")
            st.rerun()
        limite = seleccionar_limite_registros(
            "Controles a mostrar",
            len(vits),
            key="clinica_limite_vitales",
            default=50,
            opciones=(10, 20, 50, 100, 150, 200),
        )
        df_vits = pd.DataFrame(vits[-limite:]).drop(columns=["paciente"], errors="ignore")
        df_vits["fecha_dt"] = df_vits["fecha"].apply(_parse_fecha_hora)
        df_vits = df_vits.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
        rename_map = {
            "fecha": "Fecha y Hora",
            "TA": "T.A.",
            "FC": "F.C.",
            "FR": "F.R.",
            "Sat": "SatO2%",
            "Temp": "Temp C",
            "HGT": "HGT",
            "observaciones": "Obs.",
            "registrado_por": "Registrado por",
        }
        df_vits = df_vits.rename(columns={k: v for k, v in rename_map.items() if k in df_vits.columns})
        with lista_plegable("Historial de signos vitales", count=len(df_vits), expanded=False, height=400):
            mostrar_dataframe_con_scroll(df_vits, height=340)

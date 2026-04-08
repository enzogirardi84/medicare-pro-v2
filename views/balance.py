import streamlit as st
import pandas as pd
from core.utils import ahora
from core.database import guardar_datos

def render_balance(paciente_sel, user):
    if not paciente_sel:
        st.info("👈 Seleccioná un paciente en el menú lateral.")
        return

    st.subheader("⚖️ Balance Hídrico Estricto")
    
    with st.form("bal", clear_on_submit=True):
        col_meta1, col_meta2, col_meta3 = st.columns(3)
        fecha_bal = col_meta1.date_input("📅 Fecha de control", value=ahora().date(), key="fecha_bal")
        hora_bal_str = col_meta2.text_input("⏰ Hora exacta (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_bal")
        turno = col_meta3.selectbox("Turno de Guardia", ["Mañana (06 a 14hs)", "Tarde (14 a 22hs)", "Noche (22 a 06hs)"])
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🟢 Ingresos (ml)")
            i_oral = st.number_input("Oral / Enteral", min_value=0, step=50, value=0)
            i_par = st.number_input("Parenteral (Sachets, Medicación)", min_value=0, step=50, value=0)
        with c2:
            st.markdown("#### 🔴 Egresos (ml)")
            e_orina = st.number_input("Diuresis (Orina)", min_value=0, step=50, value=0)
            e_dren = st.number_input("Drenajes / Sondas", min_value=0, step=50, value=0)
            e_perd = st.number_input("Pérdidas Insensibles / Catarsis", min_value=0, step=50, value=0)
        
        if st.form_submit_button("💾 Guardar Balance y Calcular Shift", use_container_width=True, type="primary"):
            hora_limpia = hora_bal_str.strip() if ":" in hora_bal_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_bal.strftime('%d/%m/%Y')} {hora_limpia}"
            ingresos = i_oral + i_par
            egresos = e_orina + e_dren + e_perd
            balance = ingresos - egresos
            
            st.session_state["balance_db"].append({
                "paciente": paciente_sel, "turno": turno, "i_oral": i_oral, "i_par": i_par,
                "e_orina": e_orina, "e_dren": e_dren, "e_perd": e_perd, "ingresos": ingresos,
                "egresos": egresos, "balance": balance, "fecha": fecha_str, "firma": user["nombre"]
            })
            guardar_datos()
            st.success(f"✅ Balance guardado → Shift: {'+' if balance >= 0 else ''}{balance} ml")
            st.rerun()

    blp = [x for x in st.session_state.get("balance_db", []) if x.get("paciente") == paciente_sel]
    
    if blp:
        st.divider()
        st.markdown("#### 📋 Historial de Balances Hídricos")
        
        df_temp = pd.DataFrame(blp)
        ultimo = df_temp["balance"].iloc[-1] if not df_temp.empty else 0
        col_met1, col_met2, col_met3 = st.columns(3)
        
        col_met1.metric("Último Shift", f"{ultimo:+} ml", 
                       delta="Retención (Alerta)" if ultimo > 0 else ("Pérdida" if ultimo < 0 else "Neutro"),
                       delta_color="inverse")
        col_met2.metric("Total balances", len(blp))
        col_met3.metric("Balance neto (últimos 3 turnos)", f"{sum(df_temp['balance'].tail(3)):+} ml")
        
        df_bal = pd.DataFrame(blp)
        df_bal['fecha_dt'] = pd.to_datetime(df_bal['fecha'], format="%d/%m/%Y %H:%M", errors='coerce')
        df_bal = df_bal.sort_values(by='fecha_dt', ascending=False).drop(columns=['fecha_dt'], errors='ignore')
        df_bal["Ingresos"] = df_bal["ingresos"].astype(str) + " ml"
        df_bal["Egresos"] = df_bal["egresos"].astype(str) + " ml"
        
        def formato_shift(val):
            if val > 0: return f"🔴 +{val} ml"
            elif val < 0: return f"🟢 {val} ml"
            else: return "⚖️ 0 ml"
        
        df_bal["Shift (Resultado)"] = df_bal["balance"].apply(formato_shift)
        df_mostrar = df_bal.rename(columns={"fecha": "Fecha y Hora", "turno": "Turno", "firma": "Enfermero/a"})
        
        with st.container(height=450, border=True):
            st.dataframe(
                df_mostrar[["Fecha y Hora", "Turno", "Ingresos", "Egresos", "Shift (Resultado)", "Enfermero/a"]],
                use_container_width=True, hide_index=True, height=450, 
                column_config={"Shift (Resultado)": st.column_config.TextColumn("Shift (Resultado)", help="🔴 Retención = Rojo | 🟢 Eliminación = Verde")}
            )
        
        st.divider()
        if st.button("🗑️ Borrar último balance", use_container_width=True, type="secondary"):
            if st.checkbox("¿Estás seguro?", key="conf_del_balance"):
                st.session_state["balance_db"].remove(blp[-1])
                guardar_datos()
                st.success("✅ Último balance eliminado")
                st.rerun()
    else:
        st.info("Aún no hay balances hídricos registrados para este paciente.")

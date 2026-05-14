"""TEST - App minima para verificar que Streamlit Cloud funciona"""
import streamlit as st

st.set_page_config(page_title="TEST Medicare", layout="centered")

st.title("✅ TEST OK")
st.success("Si ves esto, Streamlit Cloud funciona correctamente.")
st.write("Esta es una app minima SIN modulos, SIN base de datos, SIN nada.")

st.button("Probá clickear este boton", width='stretch')
st.caption("Si ves este texto y el boton funciona, el problema esta en el codigo de Medicare Pro.")

import streamlit as st

from common import load_header_title, load_logo

load_header_title()
load_logo()

st.title("🔥 Riesgo de incendio forestal")
st.info(
    "Todavía no implementado. El plan es usar el histórico de área quemada de EFFIS "
    "(Copernicus) — ver el README, sección Next steps."
)

import streamlit as st

from common import load_header_title, load_logo

load_header_title()
load_logo()

st.title("🌵 Riesgo de sequía")
st.info(
    "Todavía no implementado. El plan es usar el SPEI Global Drought Monitor (CSIC) "
    "con el mismo enfoque de recorte por municipio que el resto de amenazas — "
    "ver el README, sección Next steps."
)

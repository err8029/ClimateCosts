import streamlit as st

from common import load_header_title, load_logo

load_header_title()
load_logo()

st.title("🔥 Riesgo de incendio forestal")
st.markdown('<p style="font-size: 17px; color: #808080;">Incendio forestal</p>', unsafe_allow_html=True)

st.divider()  # 👈 Draws a horizontal rule

# Remove whitespace from the top of the page and sidebar
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
        </style>
        """, unsafe_allow_html=True)

st.info(
    "Todavía no implementado. El plan es usar el histórico de área quemada de EFFIS "
    "(Copernicus) — ver el README, sección Next steps."
)

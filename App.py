import streamlit as st

st.set_page_config(layout="wide", page_title="ClimateCosts", page_icon="🌍")

paginas = st.navigation([
    st.Page("pages/heat.py", title="Calor", icon="🌡️"),
    st.Page("pages/flood.py", title="Inundación", icon="🌊"),
    st.Page("pages/drought.py", title="Sequía", icon="🌵"),
    st.Page("pages/wildfire.py", title="Incendios", icon="🔥"),
    st.Page("pages/combined.py", title="Combinado", icon="🗺️"),
])
paginas.run()

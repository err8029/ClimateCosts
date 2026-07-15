# main.py
import streamlit as st

from auth import requerir_login

# 1. La configuración de página DEBE ser siempre el primer comando ejecutado
st.set_page_config(layout="wide", page_title="Apollo", page_icon="🌍")

# 2. El logo (globo terráqueo, assets/logo.png) y el texto "APOLLO" se muestran vía
# common.load_logo() dentro de cada página - ver pages/*.py - no aquí, porque
# st.navigation todavía no ha enrutado a ninguna página en este punto del script.

# 3. Definición de la arquitectura de tus páginas (quedan limpias sin CSS repetido).
# st.navigation() DEBE llamarse siempre, en cada ejecución del script -incluso antes de
# iniciar sesión- para que Streamlit registre correctamente los grupos/páginas de la
# barra lateral; solo se retrasa paginas.run() (más abajo) hasta autenticarse.
paginas = st.navigation(
    {
        "Por riesgo:": [
            st.Page("pages/heat.py", title="Calor", icon="🌡️", default=True),
            st.Page("pages/flood.py", title="Inundación", icon="🌊"),
            st.Page("pages/drought.py", title="Sequía", icon="🌵"),
            st.Page("pages/wildfire.py", title="Incendios", icon="🔥"),
        ],
        "Combinado:": [
            st.Page("pages/combined.py", title="Perfiles", icon="🗺️"),
        ]
    }
)

# 4. Bloquea el resto de la app hasta que se introduzcan credenciales correctas (ver auth.py).
requerir_login()

# 5. Se ejecuta el enrutador global
paginas.run()


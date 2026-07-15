import streamlit as st

from common import rango_columna, construir_mapa_combinado, load_header_title, load_logo

load_header_title()
load_logo()

st.title("🗺️ Vista combinada")
st.caption(
    "Superpone las capas de riesgo disponibles en un único mapa. Usa el control de "
    "capas (arriba a la derecha del mapa) para activar o desactivar cada una."
)

RUTA_CALOR = "heat/output/municipios_heatwave_risk_2030_rcp4_5_lite.geojson"
RUTA_INUNDACION = "flood/output/municipios_inundacion_lite.geojson"
RUTA_SEQUIA = "drought/output/municipios_drought_risk_2030_rcp4_5_lite.geojson"
RUTA_INCENDIO = "wildfire/output/municipios_wildfire_risk_2030_rcp4_5_lite.geojson"

col_calor, col_inundacion, col_sequia, col_incendio = st.columns(4)
mostrar_calor = col_calor.checkbox("Riesgo de mortalidad por calor (2030, RCP4.5)", value=True)
mostrar_inundacion = col_inundacion.checkbox("Riesgo de inundación (100 años)", value=True)
mostrar_sequia = col_sequia.checkbox("Duración de sequía (2030, RCP4.5)", value=True)
mostrar_incendio = col_incendio.checkbox("Riesgo de incendio forestal (2030, RCP4.5)", value=True)

if not any((mostrar_calor, mostrar_inundacion, mostrar_sequia, mostrar_incendio)):
    st.warning("Activa al menos una capa para verla en el mapa.")
else:
    vmin_calor, vmax_calor = rango_columna((RUTA_CALOR,), "heat_mortality_risk")
    vmin_inund, vmax_inund = rango_columna((RUTA_INUNDACION,), "flood_risk_t100")
    vmin_sequia, vmax_sequia = rango_columna((RUTA_SEQUIA,), "drought_duration_months")
    vmin_incendio, vmax_incendio = rango_columna((RUTA_INCENDIO,), "wildfire_risk")

    capas = []
    if mostrar_calor:
        capas.append((RUTA_CALOR, "heat_mortality_risk", vmin_calor, vmax_calor, "Riesgo de calor", True))
    if mostrar_inundacion:
        capas.append((RUTA_INUNDACION, "flood_risk_t100", vmin_inund, vmax_inund, "Riesgo de inundación", True))
    if mostrar_sequia:
        capas.append((RUTA_SEQUIA, "drought_duration_months", vmin_sequia, vmax_sequia, "Duración de sequía", True))
    if mostrar_incendio:
        capas.append((RUTA_INCENDIO, "wildfire_risk", vmin_incendio, vmax_incendio, "Riesgo de incendio", True))

    construir_mapa_combinado(tuple(capas)).to_streamlit(height=700)

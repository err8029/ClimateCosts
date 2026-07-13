import streamlit as st

from common import rango_columna, construir_mapa_combinado

st.title("🗺️ Vista combinada")
st.caption(
    "Superpone las capas de riesgo disponibles en un único mapa. Usa el control de "
    "capas (arriba a la derecha del mapa) para activar o desactivar cada una."
)

RUTA_CALOR = "heat/output/municipios_heatwave_risk_2030_rcp4_5_lite.geojson"
RUTA_INUNDACION = "flood/output/municipios_inundacion_lite.geojson"

col_calor, col_inundacion = st.columns(2)
mostrar_calor = col_calor.checkbox("Riesgo de mortalidad por calor (2030, RCP4.5)", value=True)
mostrar_inundacion = col_inundacion.checkbox("Riesgo de inundación (100 años)", value=True)

if not mostrar_calor and not mostrar_inundacion:
    st.warning("Activa al menos una capa para verla en el mapa.")
else:
    vmin_calor, vmax_calor = rango_columna((RUTA_CALOR,), "heat_mortality_risk")
    vmin_inund, vmax_inund = rango_columna((RUTA_INUNDACION,), "flood_risk_t100")

    capas = []
    if mostrar_calor:
        capas.append((RUTA_CALOR, "heat_mortality_risk", vmin_calor, vmax_calor, "Riesgo de calor", True))
    if mostrar_inundacion:
        capas.append((RUTA_INUNDACION, "flood_risk_t100", vmin_inund, vmax_inund, "Riesgo de inundación", True))

    construir_mapa_combinado(tuple(capas)).to_streamlit(height=700)

st.info(
    "Sequía e incendios forestales se añadirán a esta vista combinada cuando estén "
    "implementados (ver README, sección Next steps)."
)

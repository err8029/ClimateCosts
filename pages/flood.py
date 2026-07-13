import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa

RUTA = "flood/output/municipios_inundacion_lite.geojson"

PERIODOS = {
    "10 años (frecuente)": "flood_risk_t10",
    "100 años (ocasional)": "flood_risk_t100",
    "500 años (excepcional)": "flood_risk_t500",
}

st.title("🌊 Riesgo de inundación")
st.caption(
    "Fracción de la población de cada municipio en zona de riesgo de inundación fluvial "
    "(MITECO/SNCZI), por periodo de retorno."
)

etiqueta_periodo = st.selectbox("Periodo de retorno", list(PERIODOS.keys()))
columna = PERIODOS[etiqueta_periodo]

# Mismo rango de color en los 3 periodos, para que se puedan comparar entre sí visualmente.
vmin, vmax = rango_columna((RUTA,), columna)

construir_mapa(RUTA, columna, vmin, vmax, etiqueta=etiqueta_periodo).to_streamlit(height=650)

st.subheader(f"Top 10 municipios con mayor riesgo – {etiqueta_periodo}")
gdf = cargar_geojson(RUTA)
top10 = gdf.nlargest(10, columna)[['NAMEUNIT', columna]].rename(columns={
    'NAMEUNIT': 'Municipio',
    columna: 'Fracción de población en riesgo',
}).round(3).reset_index(drop=True)
st.dataframe(top10, width="stretch")

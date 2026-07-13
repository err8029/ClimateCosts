import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, load_header_title, load_logo

# Execute the header styling at the start of the script layout loop
load_header_title()
load_logo()

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

st.subheader(f"Población afectada proyectada, 2030 → 2050 – {etiqueta_periodo}")
st.caption(
    "La zona de inundación en sí no cambia (España no tiene proyecciones oficiales de "
    "zonas inundables a futuro): lo que varía es cuánta gente viviría expuesta a ese "
    "mismo riesgo físico, según la proyección de población por provincia (INE)."
)
columna_2030 = f"{columna}_poblacion_afectada_2030"
columna_2050 = f"{columna}_poblacion_afectada_2050"
proyeccion = gdf[['NAMEUNIT', columna_2030, columna_2050]].dropna()
proyeccion['Incremento'] = proyeccion[columna_2050] - proyeccion[columna_2030]
proyeccion = proyeccion.nlargest(10, 'Incremento').rename(columns={
    'NAMEUNIT': 'Municipio',
    columna_2030: 'Afectados 2030',
    columna_2050: 'Afectados 2050',
}).round(0).reset_index(drop=True)
st.dataframe(proyeccion, width="stretch")

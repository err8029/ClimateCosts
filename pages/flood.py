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
    "Población afectada por zona de riesgo de inundación fluvial (MITECO/SNCZI), por "
    "periodo de retorno. La zona de inundación en sí no cambia (España no tiene "
    "proyecciones oficiales de zonas inundables a futuro): lo que varía entre 2030 y "
    "2050 es cuánta gente viviría expuesta a ese mismo riesgo físico, según la "
    "proyección de población por provincia (INE)."
)

etiqueta_periodo = st.selectbox("Periodo de retorno", list(PERIODOS.keys()))
columna_base = PERIODOS[etiqueta_periodo]
columna_2030 = f"{columna_base}_poblacion_afectada_2030"
columna_2050 = f"{columna_base}_poblacion_afectada_2050"

# Mismo rango de color en 2030 y 2050, para que se puedan comparar entre sí visualmente
# (si no, cada mapa reescalaría sus propios colores).
vmin, vmax = rango_columna((RUTA,), columna_2030)
vmin_2050, vmax_2050 = rango_columna((RUTA,), columna_2050)
vmin, vmax = min(vmin, vmin_2050), max(vmax, vmax_2050)

gdf = cargar_geojson(RUTA)


def tabla_top10(columna, etiqueta):
    top10 = gdf.nlargest(10, columna)[['NAMEUNIT', columna]].rename(columns={
        'NAMEUNIT': 'Municipio',
        columna: etiqueta,
    }).round(0).reset_index(drop=True)
    st.dataframe(top10, width="stretch")


col_2030, col_2050 = st.columns(2)

with col_2030:
    st.subheader("2030")
    construir_mapa(RUTA, columna_2030, vmin, vmax, etiqueta=f"{etiqueta_periodo} (2030)").to_streamlit(height=600)
    st.subheader(f"Top 10 municipios – {etiqueta_periodo}, 2030")
    tabla_top10(columna_2030, "Afectados 2030")

with col_2050:
    st.subheader("2050")
    construir_mapa(RUTA, columna_2050, vmin, vmax, etiqueta=f"{etiqueta_periodo} (2050)").to_streamlit(height=600)
    st.subheader(f"Top 10 municipios – {etiqueta_periodo}, 2050")
    tabla_top10(columna_2050, "Afectados 2050")

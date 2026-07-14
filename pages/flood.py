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

# Mismas 10 ciudades más pobladas de España que en heat.py (mismo razonamiento: la
# población no depende del hazard, así que se fija la lista en vez de cargarla aquí).
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']

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
vmin_2030, vmax_2030 = rango_columna((RUTA,), columna_2030)
vmin_2050, vmax_2050 = rango_columna((RUTA,), columna_2050)
vmin, vmax = min(vmin_2030, vmin_2050), max(vmax_2030, vmax_2050)

datos = cargar_geojson(RUTA)[['ine_code', 'NAMEUNIT', columna_2030, columna_2050]]
datos = datos.dropna(subset=[columna_2030, columna_2050])
datos['incremento'] = datos[columna_2050] - datos[columna_2030]


def formatear_tabla(tabla):
    return tabla[['NAMEUNIT', columna_2030, columna_2050, 'incremento']].rename(columns={
        'NAMEUNIT': 'Municipio',
        columna_2030: 'Afectados 2030',
        columna_2050: 'Afectados 2050',
        'incremento': 'Incremento',
    }).round(0).reset_index(drop=True)


mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    construir_mapa(RUTA, columna_2030, vmin, vmax, etiqueta=f"{etiqueta_periodo} (2030)").to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    construir_mapa(RUTA, columna_2050, vmin, vmax, etiqueta=f"{etiqueta_periodo} (2050)").to_streamlit(height=600)

tabla_incrementos, tabla_ciudades = st.columns(2)

with tabla_incrementos:
    st.subheader(f"Top 10 mayores incrementos – {etiqueta_periodo}")
    top_incrementos = datos.sort_values('incremento', ascending=False).head(10)
    st.dataframe(formatear_tabla(top_incrementos), width="stretch")

with tabla_ciudades:
    st.subheader(f"Top 10 ciudades españolas – {etiqueta_periodo}")
    ciudades = datos[datos['ine_code'].isin(TOP10_CIUDADES)]
    # Mismo orden que TOP10_CIUDADES (de mayor a menor población), no alfabético ni por incremento.
    ciudades = ciudades.set_index('ine_code').loc[TOP10_CIUDADES].reset_index()
    st.dataframe(formatear_tabla(ciudades), width="stretch")

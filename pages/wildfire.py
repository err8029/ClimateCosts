import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, load_header_title, load_logo

load_header_title()
load_logo()

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}
VARIABLES = {
    "Riesgo de incendio forestal": "wildfire_risk",
    "Índice de peligro de incendio (Canadian FWI)": "fire_weather_index",
    "Días/año de peligro alto": "high_fire_danger_days",
}

# Mismas 10 ciudades más pobladas de España que en heat.py/flood.py/drought.py.
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']


def ruta_geojson(año, escenario):
    return f"wildfire/output/municipios_wildfire_risk_{año}_{escenario}_lite.geojson"


def combinar_años(escenario, columna):
    datos_2030 = cargar_geojson(ruta_geojson(2030, escenario))[['ine_code', 'NAMEUNIT', columna]]
    datos_2050 = cargar_geojson(ruta_geojson(2050, escenario))[['ine_code', columna]]

    combinado = datos_2030.merge(datos_2050, on='ine_code', suffixes=('_2030', '_2050'))
    combinado = combinado.dropna(subset=[f'{columna}_2030', f'{columna}_2050'])
    combinado['incremento'] = combinado[f'{columna}_2050'] - combinado[f'{columna}_2030']
    return combinado


def formatear_tabla(datos, columna, etiqueta):
    return datos[['NAMEUNIT', f'{columna}_2030', f'{columna}_2050', 'incremento']].rename(columns={
        'NAMEUNIT': 'Municipio',
        f'{columna}_2030': f'{etiqueta} 2030',
        f'{columna}_2050': f'{etiqueta} 2050',
        'incremento': 'Incremento',
    }).round(3).reset_index(drop=True)


def tabla_top_incrementos(escenario, columna, etiqueta, n=10):
    combinado = combinar_años(escenario, columna)
    top = combinado.sort_values('incremento', ascending=False).head(n)
    return formatear_tabla(top, columna, etiqueta)


def tabla_top_ciudades(escenario, columna, etiqueta):
    combinado = combinar_años(escenario, columna)
    # A diferencia de heat/drought, algunas de las 10 ciudades más grandes (p.ej. València,
    # Alacant/Alicante) caen en la franja costera sin dato de este indicador (ver README,
    # Known limitations): reindex+dropna en vez de .loc[], que fallaría con KeyError.
    ciudades = combinado.set_index('ine_code').reindex(TOP10_CIUDADES).dropna().reset_index()
    return formatear_tabla(ciudades, columna, etiqueta)


st.title("🔥 Riesgo de incendio forestal")
st.markdown(
    '<p style="font-size: 17px; color: #808080;">Riesgo de incendio forestal en periodo '
    "estival, a partir del Canadian Fire Weather Index y los días/año de peligro alto "
    "(sis-ecde-climate-indicators, Copernicus/EEA), combinados con la población expuesta "
    "por municipio, para los escenarios RCP4.5 y RCP8.5 y los años 2030 y 2050.</p>",
    unsafe_allow_html=True,
)

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

columna_escenario, columna_variable = st.columns(2)
etiqueta_escenario = columna_escenario.selectbox("Escenario (RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]
etiqueta_variable = columna_variable.selectbox("Variable", list(VARIABLES.keys()))
columna = VARIABLES[etiqueta_variable]

vmin, vmax = rango_columna(
    tuple(ruta_geojson(año, esc) for esc in ESCENARIOS.values() for año in AÑOS),
    columna,
)

mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    construir_mapa(ruta_geojson(2030, escenario), columna, vmin, vmax, etiqueta=etiqueta_variable).to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    construir_mapa(ruta_geojson(2050, escenario), columna, vmin, vmax, etiqueta=etiqueta_variable).to_streamlit(height=600)

tabla_incrementos, tabla_ciudades = st.columns(2)

with tabla_incrementos:
    st.subheader(f"Top 10 mayores incrementos – {etiqueta_variable}")
    st.dataframe(tabla_top_incrementos(escenario, columna, etiqueta_variable), width="stretch")

with tabla_ciudades:
    st.subheader(f"Top 10 ciudades españolas – {etiqueta_variable}")
    st.dataframe(tabla_top_ciudades(escenario, columna, etiqueta_variable), width="stretch")

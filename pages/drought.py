import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, load_header_title, load_logo

# Execute the header styling at the start of the script layout loop
load_header_title()
load_logo()

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}
VARIABLES = {
    "Duración de la sequía (meses/año)": "drought_duration_months",
    "Magnitud de la sequía (índice SPI-3)": "drought_magnitude",
}

# Mismas 10 ciudades más pobladas de España que en heat.py/flood.py.
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']


def ruta_geojson(año, escenario):
    return f"drought/output/municipios_drought_risk_{año}_{escenario}_lite.geojson"


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
    }).round(2).reset_index(drop=True)


def tabla_top_incrementos(escenario, columna, etiqueta, n=10):
    combinado = combinar_años(escenario, columna)
    top = combinado.sort_values('incremento', ascending=False).head(n)
    return formatear_tabla(top, columna, etiqueta)


def tabla_top_ciudades(escenario, columna, etiqueta):
    combinado = combinar_años(escenario, columna)
    ciudades = combinado[combinado['ine_code'].isin(TOP10_CIUDADES)]
    ciudades = ciudades.set_index('ine_code').loc[TOP10_CIUDADES].reset_index()
    return formatear_tabla(ciudades, columna, etiqueta)


st.title("🌵 Riesgo de sequía")
st.caption(
    "Duración (meses/año en sequía) y magnitud (severidad, índice SPI-3) de la sequía "
    "meteorológica, según sis-ecde-climate-indicators (Copernicus/EEA), derivado de CORDEX. "
    "SPI-3 mide solo el déficit de precipitación (no la evapotranspiración, a diferencia del "
    "SPEI del resto de fuentes de sequía), ver README. Cada valor es la media de una ventana "
    "climatológica de 20 años centrada en el año objetivo (2021-2040 para 2030, 2041-2060 "
    "para 2050), no el dato de un año suelto (muy ruidoso año a año)."
)

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

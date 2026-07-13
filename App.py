import streamlit as st
import geopandas as gpd
import pandas as pd
import leafmap.foliumap as leafmap
from branca.colormap import LinearColormap

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}
VARIABLES = {
    "Riesgo de mortalidad por calor": "heat_mortality_risk",
    "Índice de calor (día, temp. máxima)": "heat_index_max_c",
    "Índice de calor (noche, temp. mínima)": "heat_index_min_c",
}


def ruta_geojson(año, escenario):
    return f"municipios_heatwave_risk_{año}_{escenario}_lite.geojson"


@st.cache_data
def cargar_datos(año, escenario):
    return gpd.read_file(ruta_geojson(año, escenario))


@st.cache_data
def rango_variable(columna):
    # Mismo rango de color en los 2 años y 2 escenarios para una misma variable, para que
    # se puedan comparar visualmente entre sí (si no, cada vista reescalaría sus propios
    # colores). El rango es específico de cada variable: mezclar la escala 0-1 de
    # heat_mortality_risk con los °C de los índices de calor no tendría sentido.
    valores = []
    for escenario in ESCENARIOS.values():
        for año in AÑOS:
            valores.append(cargar_datos(año, escenario)[columna])
    todos = pd.concat(valores)
    return todos.min(), todos.max()


def mapa_municipios(año, escenario, columna, vmin, vmax):
    gdf = cargar_datos(año, escenario)

    m = leafmap.Map(center=[40, -3], zoom=5.5)

    colormap = LinearColormap(
        colors=['blue', 'green', 'yellow', 'orange', 'red'],
        vmin=vmin,
        vmax=vmax,
    )
    colormap.caption = columna

    def style_function(feature):
        valor = feature["properties"][columna]
        return {
            # Algunos municipios no tienen valor (ver README, "Known limitations"): se
            # pintan en gris en vez de pasarle None a colormap(), que falla al renderizar.
            "fillColor": colormap(valor) if valor is not None else "#808080",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.8,
        }

    m.add_geojson(
        ruta_geojson(año, escenario),
        layer_name=columna,
        fields=["NAMEUNIT", columna],
        style_function=style_function,
    )
    m.add_child(colormap)
    return m


st.set_page_config(layout="wide")
st.title("Heat Mortality Risk – Spanish Municipalities")

columna_escenario, columna_variable = st.columns(2)
etiqueta_escenario = columna_escenario.selectbox("Escenario (SSP/RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]
etiqueta_variable = columna_variable.selectbox("Variable", list(VARIABLES.keys()))
columna = VARIABLES[etiqueta_variable]

vmin, vmax = rango_variable(columna)

mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    mapa_municipios(2030, escenario, columna, vmin, vmax).to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    mapa_municipios(2050, escenario, columna, vmin, vmax).to_streamlit(height=600)

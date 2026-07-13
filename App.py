import streamlit as st
import geopandas as gpd
import pandas as pd
import leafmap.foliumap as leafmap
from branca.colormap import LinearColormap

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}


def ruta_geojson(año, escenario):
    return f"municipios_heatwave_risk_{año}_{escenario}.geojson"


@st.cache_data
def cargar_datos(año, escenario):
    return gpd.read_file(ruta_geojson(año, escenario))


@st.cache_data
def rango_global():
    # Mismo rango de color en las 4 combinaciones, para que se puedan comparar
    # visualmente entre sí (si no, cada vista reescalaría sus propios colores).
    valores = []
    for escenario in ESCENARIOS.values():
        for año in AÑOS:
            valores.append(cargar_datos(año, escenario)["heat_mortality_risk"])
    todos = pd.concat(valores)
    return todos.min(), todos.max()


st.set_page_config(layout="wide")
st.title("Heat Mortality Risk – Spanish Municipalities")

columna_año, columna_escenario = st.columns(2)
año = columna_año.selectbox("Año", AÑOS)
etiqueta_escenario = columna_escenario.selectbox("Escenario (SSP/RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]

geojson_name = ruta_geojson(año, escenario)
gdf = cargar_datos(año, escenario)

vmin, vmax = rango_global()

m = leafmap.Map(center=[40, -3], zoom=6)

colormap = LinearColormap(
    colors=['blue', 'green', 'yellow', 'orange', 'red'],
    vmin=vmin,
    vmax=vmax,
)
colormap.caption = "Heat Mortality Risk"

def style_function(feature):
    valor = feature["properties"]["heat_mortality_risk"]
    return {
        # ~118 municipios have no value (see README known limitations): fall back to gray
        # instead of passing None into colormap(), which crashes on render.
        "fillColor": colormap(valor) if valor is not None else "#808080",
        "color": "black",
        "weight": 0.5,
        "fillOpacity": 0.8,
    }

m.add_geojson(
    geojson_name,
    layer_name="Heat Mortality Risk",
    fields=["NAMEUNIT", "heat_mortality_risk"],
    style_function=style_function,
)

m.add_child(colormap)

m.to_streamlit(height=700)

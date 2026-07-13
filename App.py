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


# Las 10 ciudades españolas más pobladas (INE, ver municipios_heatwave_risk_2030_rcp4_5.geojson
# columna 'poblacion' - la población no varía entre escenario/año en este proyecto, así que
# el ranking es el mismo para las 4 combinaciones). Se fija esta lista en vez de calcularla en
# la app para no tener que cargar el geojson completo (mucho más pesado que el lite) solo para
# leer población.
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']


def combinar_años(escenario, columna):
    # Se cruza por ine_code, no por NAMEUNIT: hay 17 nombres de municipio duplicados a
    # nivel nacional (p.ej. "Mieres" existe en dos provincias), y cruzar solo por nombre
    # mezclaría datos de municipios distintos.
    datos_2030 = cargar_datos(2030, escenario)[['ine_code', 'NAMEUNIT', columna]]
    datos_2050 = cargar_datos(2050, escenario)[['ine_code', columna]]

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
    ciudades = combinado[combinado['ine_code'].isin(TOP10_CIUDADES)]
    # Mismo orden que TOP10_CIUDADES (de mayor a menor población), no alfabético ni por incremento.
    ciudades = ciudades.set_index('ine_code').loc[TOP10_CIUDADES].reset_index()
    return formatear_tabla(ciudades, columna, etiqueta)


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

tabla_incrementos, tabla_ciudades = st.columns(2)

with tabla_incrementos:
    st.subheader(f"Top 10 mayores incrementos – {etiqueta_variable}")
    st.dataframe(tabla_top_incrementos(escenario, columna, etiqueta_variable), width="stretch")

with tabla_ciudades:
    st.subheader(f"Top 10 ciudades españolas – {etiqueta_variable}")
    st.dataframe(tabla_top_ciudades(escenario, columna, etiqueta_variable), width="stretch")

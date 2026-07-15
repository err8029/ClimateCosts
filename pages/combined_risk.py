import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, construir_mapa_combinado, load_header_title, load_logo

load_header_title()
load_logo()

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}

# Mismas 10 ciudades más pobladas de España que en heat.py/flood.py/drought.py/wildfire.py.
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']


def ruta_combinado(año, escenario):
    return f"combined/output/municipios_combined_risk_{año}_{escenario}_lite.geojson"


def combinar_años(escenario):
    datos_2030 = cargar_geojson(ruta_combinado(2030, escenario))[['ine_code', 'NAMEUNIT', 'combined_risk']]
    datos_2050 = cargar_geojson(ruta_combinado(2050, escenario))[['ine_code', 'combined_risk']]

    combinado = datos_2030.merge(datos_2050, on='ine_code', suffixes=('_2030', '_2050'))
    combinado = combinado.dropna(subset=['combined_risk_2030', 'combined_risk_2050'])
    combinado['incremento'] = combinado['combined_risk_2050'] - combinado['combined_risk_2030']
    return combinado


def formatear_tabla(datos):
    return datos[['NAMEUNIT', 'combined_risk_2030', 'combined_risk_2050', 'incremento']].rename(columns={
        'NAMEUNIT': 'Municipio',
        'combined_risk_2030': 'Riesgo combinado 2030',
        'combined_risk_2050': 'Riesgo combinado 2050',
        'incremento': 'Incremento',
    }).round(3).reset_index(drop=True)


st.title("🗺️ Riesgo combinado")
st.caption(
    "Combina los 4 riesgos (calor, inundación, sequía, incendio) en un único indicador "
    "por municipio, ponderado por hazard (calor 40%, inundación 30%, sequía e incendio "
    "15% cada uno - los mismos pesos que usa el impacto financiero, ver su página y el "
    "README para las fuentes). Es una suma ponderada, no un producto: que un componente "
    "sea 0 no anula el resto. Cada hazard aporta una variable representativa normalizada "
    "0-1 con un rango propio (no reutiliza directamente los números mostrados en la "
    "página de cada hazard) - ver README. Solo se calcula donde los 4 componentes tienen "
    "dato: los municipios sin alguno (sobre todo por el hueco costero de incendio, ver su "
    "página) quedan sin riesgo combinado."
)

etiqueta_escenario = st.selectbox("Escenario (RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]

vmin, vmax = rango_columna(
    tuple(ruta_combinado(año, esc) for esc in ESCENARIOS.values() for año in AÑOS),
    "combined_risk",
)

mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    construir_mapa(ruta_combinado(2030, escenario), "combined_risk", vmin, vmax, etiqueta="Riesgo combinado").to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    construir_mapa(ruta_combinado(2050, escenario), "combined_risk", vmin, vmax, etiqueta="Riesgo combinado").to_streamlit(height=600)

tabla_incrementos, tabla_ciudades = st.columns(2)
combinado_años = combinar_años(escenario)

with tabla_incrementos:
    st.subheader("Top 10 mayores incrementos")
    top_incrementos = combinado_años.sort_values('incremento', ascending=False).head(10)
    st.dataframe(formatear_tabla(top_incrementos), width="stretch")

with tabla_ciudades:
    st.subheader("Top 10 ciudades españolas")
    ciudades = combinado_años.set_index('ine_code').reindex(TOP10_CIUDADES).dropna().reset_index()
    st.dataframe(formatear_tabla(ciudades), width="stretch")

st.divider()

st.title("🗺️ Vista combinada")
st.caption(
    "Superpone las capas de riesgo disponibles en un único mapa. Usa el control de "
    "capas (arriba a la derecha del mapa) para activar o desactivar cada una."
)

RUTA_CALOR = "heat/output/municipios_heatwave_risk_2030_rcp4_5_lite.geojson"
RUTA_INUNDACION = "flood/output/municipios_inundacion_lite.geojson"
RUTA_SEQUIA = "drought/output/municipios_drought_risk_2030_rcp4_5_lite.geojson"
RUTA_INCENDIO = "wildfire/output/municipios_wildfire_risk_2030_rcp4_5_lite.geojson"

col_calor, col_inundacion, col_sequia, col_incendio = st.columns(4)
mostrar_calor = col_calor.checkbox("Riesgo de mortalidad por calor (2030, RCP4.5)", value=True)
mostrar_inundacion = col_inundacion.checkbox("Riesgo de inundación (100 años)", value=True)
mostrar_sequia = col_sequia.checkbox("Duración de sequía (2030, RCP4.5)", value=True)
mostrar_incendio = col_incendio.checkbox("Riesgo de incendio forestal (2030, RCP4.5)", value=True)

if not any((mostrar_calor, mostrar_inundacion, mostrar_sequia, mostrar_incendio)):
    st.warning("Activa al menos una capa para verla en el mapa.")
else:
    vmin_calor, vmax_calor = rango_columna((RUTA_CALOR,), "heat_mortality_risk")
    vmin_inund, vmax_inund = rango_columna((RUTA_INUNDACION,), "flood_risk_t100")
    vmin_sequia, vmax_sequia = rango_columna((RUTA_SEQUIA,), "drought_duration_months")
    vmin_incendio, vmax_incendio = rango_columna((RUTA_INCENDIO,), "wildfire_risk")

    capas = []
    if mostrar_calor:
        capas.append((RUTA_CALOR, "heat_mortality_risk", vmin_calor, vmax_calor, "Riesgo de calor", True))
    if mostrar_inundacion:
        capas.append((RUTA_INUNDACION, "flood_risk_t100", vmin_inund, vmax_inund, "Riesgo de inundación", True))
    if mostrar_sequia:
        capas.append((RUTA_SEQUIA, "drought_duration_months", vmin_sequia, vmax_sequia, "Duración de sequía", True))
    if mostrar_incendio:
        capas.append((RUTA_INCENDIO, "wildfire_risk", vmin_incendio, vmax_incendio, "Riesgo de incendio", True))

    construir_mapa_combinado(tuple(capas)).to_streamlit(height=700)

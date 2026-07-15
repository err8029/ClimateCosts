import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, load_header_title, load_logo

load_header_title()
load_logo()

AÑOS = [2030, 2050]
ESCENARIOS = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}

# "Total" domina siempre a favor de las ciudades más grandes (crece con la población);
# "Per cápita" no depende del tamaño del municipio (ver combined/2_financial_impact.py) y
# reordena hacia dónde el riesgo climático amenaza la mayor PROPORCIÓN de la economía
# local, no solo dónde hay más euros en términos absolutos - las dos vistas responden
# preguntas distintas, por eso se ofrecen ambas en vez de sustituir una por otra.
VARIABLES = {
    "Impacto total (€)": {
        'columna': 'financial_impact_eur',
        'escala_log': True,  # cola muy larga (Madrid/Barcelona vs. el resto): sin escala
        # log el mapa queda casi monocolor salvo un puñado de grandes ciudades.
        'divisor': 1_000_000,
        'sufijo': ' (M€)',
        'columna_pib': 'valor_economico_eur',
        'etiqueta_pib': 'PIB previsto',
    },
    "Impacto per cápita (€/habitante)": {
        'columna': 'financial_impact_eur_per_capita',
        'escala_log': False,  # no depende de la población: sin la cola larga del total,
        # la escala lineal ya reparte bien el contraste.
        'divisor': 1,
        'sufijo': ' (€/hab.)',
        'columna_pib': 'pib_per_capita',
        'etiqueta_pib': 'PIB per cápita previsto',
    },
}

# Mismas 10 ciudades más pobladas de España que en heat.py/flood.py/drought.py/wildfire.py.
TOP10_CIUDADES = ['28079', '08019', '46250', '50297', '41091', '29067', '30030', '07040', '03014', '48020']


def ruta_impacto(año, escenario):
    return f"combined/output/municipios_financial_impact_{año}_{escenario}_lite.geojson"


def combinar_años(escenario, columna, columna_pib):
    columnas = ['ine_code', 'NAMEUNIT', columna, columna_pib, 'combined_risk']
    datos_2030 = cargar_geojson(ruta_impacto(2030, escenario))[columnas]
    datos_2050 = cargar_geojson(ruta_impacto(2050, escenario))[[c for c in columnas if c != 'NAMEUNIT']]

    combinado = datos_2030.merge(datos_2050, on='ine_code', suffixes=('_2030', '_2050'))
    combinado = combinado.dropna(subset=[f'{columna}_2030', f'{columna}_2050'])
    combinado['incremento'] = combinado[f'{columna}_2050'] - combinado[f'{columna}_2030']
    # Puntos porcentuales de riesgo combinado (no % de variación del impacto en €): cuánto
    # ha crecido la FRACCIÓN de PIB en riesgo, independientemente de cuánto haya crecido el
    # PIB previsto en sí - una fila puede tener un incremento en € grande solo porque el PIB
    # de base creció, sin que el riesgo relativo haya cambiado mucho; esta columna aísla esa
    # diferencia.
    combinado['incremento_pp'] = (combinado['combined_risk_2050'] - combinado['combined_risk_2030']) * 100
    return combinado


def formatear_tabla(datos, columna, divisor, sufijo, columna_pib, etiqueta_pib):
    tabla = datos[[
        'NAMEUNIT', f'{columna}_2030', f'{columna}_2050', 'incremento',
        f'{columna_pib}_2030', f'{columna_pib}_2050', 'incremento_pp',
    ]].rename(columns={
        'NAMEUNIT': 'Municipio',
        f'{columna}_2030': f'Impacto 2030{sufijo}',
        f'{columna}_2050': f'Impacto 2050{sufijo}',
        'incremento': f'Incremento{sufijo}',
        f'{columna_pib}_2030': f'{etiqueta_pib} 2030{sufijo}',
        f'{columna_pib}_2050': f'{etiqueta_pib} 2050{sufijo}',
        'incremento_pp': 'Incremento riesgo (pp)',
    })
    for c in tabla.columns[1:-1]:  # todas menos Municipio e Incremento riesgo (pp)
        tabla[c] = (tabla[c] / divisor).round(1)
    tabla['Incremento riesgo (pp)'] = tabla['Incremento riesgo (pp)'].round(2)
    return tabla.reset_index(drop=True)


st.title("💶 Impacto financiero")
st.caption(
    "Proxy del valor económico expuesto a los 4 riesgos, ponderado por hazard según su "
    "coste económico relativo (calor 40%, inundación 30%, sequía e incendio 15% cada uno "
    "- los mismos pesos que el riesgo combinado, ver su página y el README para las "
    "fuentes y limitaciones): "
    "`impacto total = población proyectada × PIB per cápita provincial (INE) × riesgo combinado`. "
    "Es un indicador relativo de exposición económica, no una predicción de daños reales. "
    "'Incremento riesgo (pp)' son puntos porcentuales de riesgo combinado (no % de "
    "variación del impacto en €): aísla cuánto ha crecido la fracción de PIB en riesgo, "
    "separado de cuánto ha crecido el PIB previsto en sí."
)

columna_escenario, columna_variable = st.columns(2)
etiqueta_escenario = columna_escenario.selectbox("Escenario (RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]
etiqueta_variable = columna_variable.selectbox("Variable", list(VARIABLES.keys()))
config_variable = VARIABLES[etiqueta_variable]
columna = config_variable['columna']
escala_log = config_variable['escala_log']
divisor = config_variable['divisor']
sufijo = config_variable['sufijo']
columna_pib = config_variable['columna_pib']
etiqueta_pib = config_variable['etiqueta_pib']

vmin, vmax = rango_columna(
    tuple(ruta_impacto(año, esc) for esc in ESCENARIOS.values() for año in AÑOS),
    columna,
)

mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    construir_mapa(ruta_impacto(2030, escenario), columna, vmin, vmax, etiqueta=etiqueta_variable, escala_log=escala_log).to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    construir_mapa(ruta_impacto(2050, escenario), columna, vmin, vmax, etiqueta=etiqueta_variable, escala_log=escala_log).to_streamlit(height=600)

tabla_incrementos, tabla_ciudades = st.columns(2)
combinado_años = combinar_años(escenario, columna, columna_pib)

with tabla_incrementos:
    st.subheader("Top 10 mayores incrementos")
    top_incrementos = combinado_años.sort_values('incremento', ascending=False).head(10)
    st.dataframe(formatear_tabla(top_incrementos, columna, divisor, sufijo, columna_pib, etiqueta_pib), width="stretch")

with tabla_ciudades:
    st.subheader("Top 10 ciudades españolas")
    ciudades = combinado_años.set_index('ine_code').reindex(TOP10_CIUDADES).dropna().reset_index()
    st.dataframe(formatear_tabla(ciudades, columna, divisor, sufijo, columna_pib, etiqueta_pib), width="stretch")

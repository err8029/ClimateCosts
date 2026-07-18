import streamlit as st

from common import cargar_geojson, rango_columna, construir_mapa, load_header_title, load_logo

load_header_title()
load_logo()

AÑOS = [2030, 2050]

# Top 10 municipios COSTEROS más poblados de España (no los 10 más poblados a secas, como
# en el resto de páginas: la mayoría de esos - Madrid, Zaragoza, Murcia, Bilbao - no tienen
# cauce/estación de marea cerca y no aparecerían aquí, ver Known limitations).
TOP10_CIUDADES_COSTERAS = ['08019', '46250', '29067', '07040', '03014', '36057', '08101', '33024', '03065', '08015']


def ruta_coastal(año):
    return f"coastal_flood/output/municipios_coastal_flood_risk_{año}_lite.geojson"


def combinar_años():
    datos_2030 = cargar_geojson(ruta_coastal(2030))[['ine_code', 'NAMEUNIT', 'sea_level_rise_m']]
    datos_2050 = cargar_geojson(ruta_coastal(2050))[['ine_code', 'sea_level_rise_m']]

    combinado = datos_2030.merge(datos_2050, on='ine_code', suffixes=('_2030', '_2050'))
    combinado = combinado.dropna(subset=['sea_level_rise_m_2030', 'sea_level_rise_m_2050'])
    combinado['incremento'] = combinado['sea_level_rise_m_2050'] - combinado['sea_level_rise_m_2030']
    return combinado


def formatear_tabla(datos):
    return datos[['NAMEUNIT', 'sea_level_rise_m_2030', 'sea_level_rise_m_2050', 'incremento']].rename(columns={
        'NAMEUNIT': 'Municipio',
        'sea_level_rise_m_2030': 'Subida nivel del mar 2030 (m)',
        'sea_level_rise_m_2050': 'Subida nivel del mar 2050 (m)',
        'incremento': 'Incremento (m)',
    }).round(3).reset_index(drop=True)


st.title("🌊 Riesgo de inundación costera")
st.caption(
    "Subida del nivel medio del mar (m), modelo GTSMv3, según sis-ecde-climate-indicators "
    "(Copernicus/EEA). A diferencia del resto de riesgos: (1) solo existe bajo el escenario "
    "SSP5-8.5 (nomenclatura CMIP6) - no hay un RCP4.5 equivalente en este indicador, así "
    "que no hay selector de escenario; (2) el dato viene de ~1.300 estaciones de marea a lo "
    "largo de la costa, no de una rejilla regular, así que se asigna a cada municipio la "
    "estación más cercana dentro de 10km - los municipios de interior (la mayoría de "
    "España) quedan sin dato a propósito, no por un hueco de cobertura. Ver README."
)

vmin, vmax = rango_columna((ruta_coastal(2030), ruta_coastal(2050)), "sea_level_rise_m")

mapa_2030, mapa_2050 = st.columns(2)

with mapa_2030:
    st.subheader("2030")
    construir_mapa(ruta_coastal(2030), "sea_level_rise_m", vmin, vmax, etiqueta="Subida nivel del mar (m)").to_streamlit(height=600)

with mapa_2050:
    st.subheader("2050")
    construir_mapa(ruta_coastal(2050), "sea_level_rise_m", vmin, vmax, etiqueta="Subida nivel del mar (m)").to_streamlit(height=600)

tabla_incrementos, tabla_ciudades = st.columns(2)
combinado_años = combinar_años()

with tabla_incrementos:
    st.subheader("Top 10 mayores incrementos")
    top_incrementos = combinado_años.sort_values('incremento', ascending=False).head(10)
    st.dataframe(formatear_tabla(top_incrementos), width="stretch")

with tabla_ciudades:
    st.subheader("Top 10 ciudades costeras españolas")
    ciudades = combinado_años.set_index('ine_code').reindex(TOP10_CIUDADES_COSTERAS).dropna().reset_index()
    st.dataframe(formatear_tabla(ciudades), width="stretch")

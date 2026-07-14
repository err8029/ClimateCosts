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
st.markdown('<p style="font-size: 17px; color: #808080;">Población afectada por zona de riesgo de inundación fluvial (MITECO/SNCZI), por periodo de retorno. La zona de inundación en sí no cambia (España no tiene proyecciones oficiales de zonas inundables a futuro): lo que varía entre 2030 y 2050 es cuánta gente viviría expuesta a ese mismo riesgo físico, según la proyección de población por provincia (INE).</p>', unsafe_allow_html=True)

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


# --- Intensidad de crecidas fluviales proyectada (Copernicus, RCP4.5/8.5) ---
#
# Indicador complementario, no un sustituto de lo anterior: MITECO mide población en zona
# fija de riesgo (sin proyección de futuro posible - España no tiene mapas de inundación
# futuros oficiales); esto mide caudal fluvial (m3/s) para un periodo de retorno, con
# escenarios de cambio climático RCP, pero sin exposición de población. Ver README.

RUTA_CAUDAL = "flood/output/municipios_river_discharge_{epoca}_{escenario}_lite.geojson"

ESCENARIOS_CAUDAL = {"RCP4.5": "rcp4_5", "RCP8.5": "rcp8_5"}
PERIODOS_CAUDAL = {
    "2 años": "river_discharge_2y",
    "5 años": "river_discharge_5y",
    "10 años": "river_discharge_10y",
    "50 años": "river_discharge_50y",
}
# El dataset de Copernicus solo trae 3 ventanas climatológicas fijas de 30 años; se usan
# las dos más cercanas al presente y a medio siglo (ver flood/5_river_discharge_risk.py),
# etiquetadas con su periodo real en vez de forzar "2030"/"2050".
EPOCAS = ["2011_2040", "2041_2070"]


def ruta_caudal(epoca, escenario):
    return RUTA_CAUDAL.format(epoca=epoca, escenario=escenario)


def combinar_epocas(escenario, columna):
    datos_e1 = cargar_geojson(ruta_caudal(EPOCAS[0], escenario))[['ine_code', 'NAMEUNIT', columna]]
    datos_e2 = cargar_geojson(ruta_caudal(EPOCAS[1], escenario))[['ine_code', columna]]

    combinado = datos_e1.merge(datos_e2, on='ine_code', suffixes=('_e1', '_e2'))
    combinado = combinado.dropna(subset=[f'{columna}_e1', f'{columna}_e2'])
    combinado['incremento'] = combinado[f'{columna}_e2'] - combinado[f'{columna}_e1']
    return combinado


def formatear_tabla_caudal(datos_tabla, columna, etiqueta):
    return datos_tabla[['NAMEUNIT', f'{columna}_e1', f'{columna}_e2', 'incremento']].rename(columns={
        'NAMEUNIT': 'Municipio',
        f'{columna}_e1': f'{etiqueta} {EPOCAS[0]}',
        f'{columna}_e2': f'{etiqueta} {EPOCAS[1]}',
        'incremento': 'Incremento',
    }).round(1).reset_index(drop=True)


st.divider()
st.title("🌊 Intensidad de crecidas fluviales proyectada")
st.caption(
    "Caudal fluvial (m³/s) esperado para un periodo de retorno dado, según "
    "sis-ecde-climate-indicators (Copernicus/EEA): modelos hidrológicos E-HYPE/VIC-WUR "
    "forzados con CORDEX bias-corregido, con escenarios RCP. Indicador complementario al "
    "de arriba: mide intensidad del caudal, no población afectada (MITECO no tiene "
    "proyecciones de futuro). Solo se calcula donde hay un cauce significativo dentro del "
    "municipio o cerca de su centroide — los municipios sin dato (gris) no tienen cauce "
    "relevante a esta resolución, no un caudal cero."
)

columna_escenario_caudal, columna_periodo_caudal = st.columns(2)
etiqueta_escenario_caudal = columna_escenario_caudal.selectbox("Escenario (RCP)", list(ESCENARIOS_CAUDAL.keys()))
escenario_caudal = ESCENARIOS_CAUDAL[etiqueta_escenario_caudal]
etiqueta_periodo_caudal = columna_periodo_caudal.selectbox("Periodo de retorno", list(PERIODOS_CAUDAL.keys()))
columna_caudal = PERIODOS_CAUDAL[etiqueta_periodo_caudal]

vmin_caudal, vmax_caudal = rango_columna(
    tuple(ruta_caudal(epoca, esc) for esc in ESCENARIOS_CAUDAL.values() for epoca in EPOCAS),
    columna_caudal,
)

mapa_e1, mapa_e2 = st.columns(2)

with mapa_e1:
    st.subheader(EPOCAS[0])
    construir_mapa(ruta_caudal(EPOCAS[0], escenario_caudal), columna_caudal, vmin_caudal, vmax_caudal, etiqueta=etiqueta_periodo_caudal).to_streamlit(height=600)

with mapa_e2:
    st.subheader(EPOCAS[1])
    construir_mapa(ruta_caudal(EPOCAS[1], escenario_caudal), columna_caudal, vmin_caudal, vmax_caudal, etiqueta=etiqueta_periodo_caudal).to_streamlit(height=600)

tabla_incrementos_caudal, tabla_ciudades_caudal = st.columns(2)

with tabla_incrementos_caudal:
    st.subheader(f"Top 10 mayores incrementos – {etiqueta_periodo_caudal}")
    combinado_caudal = combinar_epocas(escenario_caudal, columna_caudal)
    top_caudal = combinado_caudal.sort_values('incremento', ascending=False).head(10)
    st.dataframe(formatear_tabla_caudal(top_caudal, columna_caudal, etiqueta_periodo_caudal), width="stretch")

with tabla_ciudades_caudal:
    st.subheader(f"Top 10 ciudades españolas – {etiqueta_periodo_caudal}")
    ciudades_caudal = combinado_caudal[combinado_caudal['ine_code'].isin(TOP10_CIUDADES)]
    ciudades_caudal = ciudades_caudal.set_index('ine_code').reindex(TOP10_CIUDADES).dropna().reset_index()
    st.dataframe(formatear_tabla_caudal(ciudades_caudal, columna_caudal, etiqueta_periodo_caudal), width="stretch")

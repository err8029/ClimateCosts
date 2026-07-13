import geopandas as gpd
import pandas as pd
import pyogrio
import requests

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python flood/3_flood_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "flood/input"
OUTPUT_DIR = "flood/output"

INE_TABLA_PROYECCION_PROVINCIAL = "36725"  # Proyección de población por provincias, serie 2026-2041 (INE)

# Zonas de riesgo de inundación fluvial (SNCZI/MITECO), "riesgo a la población",
# para tres periodos de retorno. Cada shapefile ya viene con el número de
# personas afectadas por municipio (NUM_AFE_MU), así que no hace falta hacer
# un solape geométrico: basta con leer la tabla de atributos.
PERIODOS = {
    'flood_risk_t10': f'{INPUT_DIR}/t10/Riesgo_POB_T010_PB_20241127.shp',
    'flood_risk_t100': f'{INPUT_DIR}/t100/Riesgo_POB_T100_PB_20241127.shp',
    'flood_risk_t500': f'{INPUT_DIR}/t500/Riesgo_POB_T500_PB_20241127.shp',
}

# 1. Cargar el mapa de municipios de toda España
municipios = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios = municipios.to_crs(epsg=4326)
municipios['ine_code'] = municipios['NATCODE'].str[-5:]
municipios['codigo_provincia'] = municipios['ine_code'].str[:2]

# 2. Factores de crecimiento de población por provincia a 2030 y 2050 (mismo enfoque que
# heat/2_heatwave_risk.py - ver ahí el razonamiento completo). Las zonas de inundación del
# SNCZI son geografía de riesgo fija (no hay proyección oficial de zonas inundables a
# futuro en España), así que lo único que se proyecta a 2030/2050 es cuánta gente viviría
# expuesta a ESE MISMO riesgo físico: la fracción de población en zona de riesgo
# (flood_risk_tXX) se mantiene constante, y solo el recuento absoluto de afectados escala
# con la población proyectada de cada provincia.
resp_prov = requests.get(
    f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{INE_TABLA_PROYECCION_PROVINCIAL}",
    params={"det": 3, "tip": "AM"},
    timeout=120,
)
resp_prov.raise_for_status()
poblacion_provincia = {}
for serie in resp_prov.json():
    metadata = {m['Variable']['Nombre']: m for m in serie['MetaData']}
    if metadata.get('Lugar de nacimiento', {}).get('Nombre') != 'Total':
        continue
    provincia_meta = metadata.get('Provincias')
    if provincia_meta is None or not provincia_meta['Codigo']:
        continue  # descarta la serie "Total Nacional", sin código de provincia
    codigo_provincia = provincia_meta['Codigo']
    for punto in serie['Data']:
        poblacion_provincia.setdefault(codigo_provincia, {})[punto['Anyo']] = punto['Valor']

factor_2030_por_provincia = {}
factor_2050_por_provincia = {}
for codigo_provincia, serie_anual in poblacion_provincia.items():
    base_2026 = serie_anual.get(2026)
    valor_2030 = serie_anual.get(2030)
    valor_2041 = serie_anual.get(2041)
    if base_2026 and valor_2030:
        factor_2030_por_provincia[codigo_provincia] = valor_2030 / base_2026
    if base_2026 and valor_2041:
        tasa_anual = (valor_2041 / base_2026) ** (1 / 15)  # 2026 -> 2041 son 15 años
        factor_2050_por_provincia[codigo_provincia] = (valor_2041 / base_2026) * (tasa_anual ** 9)  # 2041 -> 2050

municipios['factor_2030'] = municipios['codigo_provincia'].map(factor_2030_por_provincia)
municipios['factor_2050'] = municipios['codigo_provincia'].map(factor_2050_por_provincia)

for columna, ruta in PERIODOS.items():
    # NUM_AFE_MU se repite en cada fragmento de geometría de un mismo municipio,
    # así que basta con quedarnos con un valor por municipio (no hay que sumar).
    tabla = pyogrio.read_dataframe(
        ruta,
        columns=['ID_MUNICIP', 'N_HAB_MUNI', 'NUM_AFE_MU'],
        read_geometry=False,
    )
    por_municipio = tabla.groupby('ID_MUNICIP', as_index=False).first()
    # N_HAB_MUNI es la población de referencia del propio estudio SNCZI (no la actual del INE),
    # y en algún caso puntual es 0 o ligeramente inferior a la población afectada: se acota
    # la fracción a [0, 1] para que el indicador sea siempre interpretable.
    fraccion = por_municipio['NUM_AFE_MU'] / por_municipio['N_HAB_MUNI'].replace(0, pd.NA)
    por_municipio['fraccion_afectada'] = fraccion.clip(upper=1.0).fillna(0.0).astype(float)

    fraccion_por_codigo = por_municipio.set_index('ID_MUNICIP')['fraccion_afectada']
    afectados_por_codigo = por_municipio.set_index('ID_MUNICIP')['NUM_AFE_MU']

    # Municipios fuera de este shapefile no están en ninguna zona de riesgo para este periodo
    municipios[columna] = municipios['ine_code'].map(fraccion_por_codigo).fillna(0.0)
    afectados_actual = municipios['ine_code'].map(afectados_por_codigo).fillna(0)
    municipios[columna + '_poblacion_afectada'] = afectados_actual.astype(int)
    municipios[columna + '_poblacion_afectada_2030'] = (afectados_actual * municipios['factor_2030']).round().astype('Int64')
    municipios[columna + '_poblacion_afectada_2050'] = (afectados_actual * municipios['factor_2050']).round().astype('Int64')

municipios.to_file(f"{OUTPUT_DIR}/municipios_inundacion.geojson", driver="GeoJSON")

# Versión ligera para la app, igual que en heat/2_heatwave_risk.py: solo las columnas que se
# visualizan, con la geometría simplificada (~90% menos peso, sin diferencia visible a escala
# de mapa nacional/de ciudad).
columnas_lite = ['NAMEUNIT', 'ine_code', 'geometry']
for columna in PERIODOS:
    columnas_lite += [columna, columna + '_poblacion_afectada', columna + '_poblacion_afectada_2030', columna + '_poblacion_afectada_2050']
municipios_lite = municipios[columnas_lite].copy()
municipios_lite['geometry'] = municipios_lite.geometry.simplify(0.001, preserve_topology=True)
municipios_lite.to_file(f"{OUTPUT_DIR}/municipios_inundacion_lite.geojson", driver="GeoJSON")

print("Zonificación de riesgo de inundación finalizada.")

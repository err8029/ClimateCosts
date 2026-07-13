import geopandas as gpd
import pandas as pd
import pyogrio

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python flood/3_flood_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "flood/input"
OUTPUT_DIR = "flood/output"

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
    municipios[columna + '_poblacion_afectada'] = municipios['ine_code'].map(afectados_por_codigo).fillna(0).astype(int)

municipios.to_file(f"{OUTPUT_DIR}/municipios_inundacion.geojson", driver="GeoJSON")
print("Zonificación de riesgo de inundación finalizada.")

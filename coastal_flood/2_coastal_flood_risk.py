import glob

import geopandas as gpd
import numpy as np
import xarray as xr
from shapely.geometry import Point

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python coastal_flood/2_coastal_flood_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "coastal_flood/input"
OUTPUT_DIR = "coastal_flood/output"

ESCENARIO = 'ssp5_8_5'
AÑOS = [2030, 2050]

# Umbral de "municipio costero": distancia máxima a la estación GTSMv3 más cercana para
# asignarle un valor. Calibrado empíricamente (no es una cifra oficial de "municipios
# costeros"): ~10km deja fuera los municipios claramente de interior mientras conserva los
# que realmente lindan con el mar o un estuario cercano (~825 de los 8.132 municipios).
# Un municipio fuera de este umbral queda con valor nulo A PROPÓSITO (no le aplica el
# indicador, no es un hueco de datos) - ver Known limitations, README.
UMBRAL_METROS = 10_000

# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios = municipios.to_crs(epsg=4326)
municipios['ine_code'] = municipios['NATCODE'].str[-5:]

# 2. Abrir el NetCDF de nivel del mar (formato "timeseries": estaciones dispersas con su
# propio lon/lat cada una, NO una rejilla regular - a diferencia de todos los demás hazards
# de este proyecto, aquí no se puede usar rio.clip().
ruta = glob.glob(f"{INPUT_DIR}/coastal_flood_raw_{ESCENARIO}/*.nc")[0]
ds = xr.open_dataset(ruta, engine="netcdf4")

estaciones = gpd.GeoDataFrame(
    {'station_id': ds['stations'].values},
    geometry=[Point(lon, lat) for lon, lat in zip(ds['lon'].values, ds['lat'].values)],
    crs="EPSG:4326",
)

# 3. Unión espacial "al más cercano": para cada municipio, la estación GTSMv3 más próxima
# (dentro del umbral). Se reproyecta a un CRS métrico (Web Mercator) solo para esta
# operación, para que el umbral en metros sea válido - geopandas avisa (con razón) de que
# sjoin_nearest sobre grados no da distancias fiables.
municipios_m = municipios.to_crs(epsg=3857)
estaciones_m = estaciones.to_crs(epsg=3857)
union = gpd.sjoin_nearest(municipios_m, estaciones_m, max_distance=UMBRAL_METROS, distance_col='distancia_estacion_m')
# sjoin_nearest puede emparejar varias estaciones a la misma distancia mínima: nos quedamos
# con una por municipio.
union = union[~union.index.duplicated(keep='first')]

for año in AÑOS:
    tabla = municipios.copy()

    nivel_por_estacion = ds.sel(time=f'{año}-01-01', method='nearest')['MSL'].to_pandas()
    station_id_por_municipio = union['station_id']
    tabla['sea_level_rise_m'] = tabla.index.map(station_id_por_municipio).map(nivel_por_estacion)
    tabla['distancia_estacion_m'] = tabla.index.map(union['distancia_estacion_m'])

    salida = f"{OUTPUT_DIR}/municipios_coastal_flood_risk_{año}.geojson"
    tabla.to_file(salida, driver="GeoJSON")

    columnas_lite = ['NAMEUNIT', 'ine_code', 'sea_level_rise_m', 'geometry']
    tabla_lite = tabla[columnas_lite].copy()
    tabla_lite['geometry'] = tabla_lite.geometry.simplify(0.001, preserve_topology=True)
    salida_lite = f"{OUTPUT_DIR}/municipios_coastal_flood_risk_{año}_lite.geojson"
    tabla_lite.to_file(salida_lite, driver="GeoJSON")

    n_con_dato = int(tabla['sea_level_rise_m'].notna().sum())
    print(f"Riesgo de inundación costera finalizado: {salida} / {salida_lite} ({n_con_dato} municipios costeros)")

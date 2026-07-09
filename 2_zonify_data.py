import geopandas as gpd
import numpy as np
import requests
import xarray as xr
import rioxarray # Extensión que permite fusionar xarray con operaciones GIS

INE_TABLA_PADRON = "29005"  # "Cifras oficiales del padrón por municipio" (INE)

# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios = gpd.read_file("municipios_espana.shp")
# Asegurar que está en coordenadas geográficas estándar (WGS84) para coincidir con Copernicus
municipios = municipios.to_crs(epsg=4326)

# Código INE de municipio (provincia + municipio) = últimos 5 dígitos del NATCODE del CNIG
municipios['ine_code'] = municipios['NATCODE'].str[-5:]

# 2. Abrir el archivo NetCDF de temperaturas descargado en el Paso 1 (ámbito nacional)
ds = xr.open_dataset("temperaturas_2030.nc", engine="netcdf4")

# Configurar el NetCDF para que reconozca las dimensiones espaciales como coordenadas GIS
ds = ds.rio.write_crs("EPSG:4326")
ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)

# 3. Extraer la temperatura máxima media de verano para cada municipio
municipios['temp_max_verano'] = 0.0

for index, row in municipios.iterrows():
    # Crear la geometría del municipio actual
    geom = [row['geometry']]

    try:
        # Recortar el raster de Copernicus usando la forma exacta del municipio
        municipio_clip = ds.rio.clip(geom, municipios.crs, drop=True)
        municipios.at[index, 'temp_max_verano'] = float(municipio_clip['tasmax'].mean())

    except Exception:
        # El grid de CMIP6 es de baja resolución (~100km): muchos municipios pequeños
        # no capturan un píxel entero, así que se les asigna el valor del punto más cercano
        municipios.at[index, 'temp_max_verano'] = float(ds['tasmax'].sel(lon=row['geometry'].centroid.x, lat=row['geometry'].centroid.y, method='nearest').mean())

municipios['temp_max_verano_c'] = municipios['temp_max_verano'] - 273.15

# 4. Obtener población por municipio (INE, Padrón - último año disponible)
# Un único municipio de tamaño pequeño puede compartir píxel de temperatura con muchos otros
# (el grid de CMIP6 es de ~100km), así que la población pondera la exposición al calor
# para reflejar cuánta gente está realmente afectada en cada municipio.
resp = requests.get(
    f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{INE_TABLA_PADRON}",
    params={"nult": 1, "det": 3, "tip": "AM"},
    timeout=120,
)
resp.raise_for_status()
poblacion_por_municipio = {}
for serie in resp.json():
    metadata = {m['Variable']['Nombre']: m for m in serie['MetaData']}
    if metadata.get('Sexo', {}).get('Nombre') != 'Total':
        continue
    ine_code = metadata['Municipios']['Codigo']
    if serie['Data']:
        poblacion_por_municipio[ine_code] = serie['Data'][0]['Valor']

municipios['poblacion'] = municipios['ine_code'].map(poblacion_por_municipio)

# 5. Indicador simple de riesgo de mortalidad por calor (proxy relativo, no una predicción real
# de muertes): combina la exposición al calor con la población expuesta, cada una normalizada
# 0-1. La población se trata en escala logarítmica porque está muy sesgada (de ~10 a >3M
# habitantes por municipio).
temp_norm = (municipios['temp_max_verano_c'] - municipios['temp_max_verano_c'].min()) / (
    municipios['temp_max_verano_c'].max() - municipios['temp_max_verano_c'].min()
)
poblacion_log = np.log1p(municipios['poblacion'])
poblacion_norm = (poblacion_log - poblacion_log.min()) / (poblacion_log.max() - poblacion_log.min())
municipios['heat_mortality_risk'] = (temp_norm + poblacion_norm) / 2

# Guardar el indicador de riesgo de mortalidad por calor por municipio
municipios.to_file("municipios_calor_2030.geojson", driver="GeoJSON")
print("Zonificación de exposición al calor finalizada.")

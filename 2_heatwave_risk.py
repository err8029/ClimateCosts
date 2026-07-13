import geopandas as gpd
import numpy as np
import requests
import xarray as xr
import rioxarray # Extensión que permite fusionar xarray con operaciones GIS
from pyproj import CRS, Transformer

INE_TABLA_PADRON = "29005"  # "Cifras oficiales del padrón por municipio" (INE)

# Misma matriz año x escenario que 1_extract_data.py: hay que generar un geojson por
# combinación para que la app pueda ofrecer los desplegables de año y escenario.
AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']


def indice_calor_f(temp_f, rh):
    """Índice de calor del National Weather Service (regresión de Rothfusz + ajustes).
    temp_f en grados Fahrenheit, rh en % (0-100)."""
    hi_simple = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))
    promedio = (hi_simple + temp_f) / 2

    hi_rothfusz = (
        -42.379 + 2.04901523 * temp_f + 10.14333127 * rh
        - 0.22475541 * temp_f * rh - 0.00683783 * temp_f ** 2
        - 0.05481717 * rh ** 2 + 0.00122874 * temp_f ** 2 * rh
        + 0.00085282 * temp_f * rh ** 2 - 0.00000199 * temp_f ** 2 * rh ** 2
    )

    aplica_baja_humedad = (rh < 13) & (temp_f >= 80) & (temp_f <= 112)
    # clip a 0: fuera del rango de aplica_baja_humedad, (17-|T-95|)/17 puede salir negativo,
    # y como np.where evalúa ambas ramas siempre, sqrt() se quejaría de valores negativos
    # que de todos modos se van a descartar.
    ajuste_baja_humedad = ((13 - rh) / 4) * np.sqrt(np.clip((17 - np.abs(temp_f - 95)) / 17, 0, None))
    hi_rothfusz = np.where(aplica_baja_humedad, hi_rothfusz - ajuste_baja_humedad, hi_rothfusz)

    aplica_alta_humedad = (rh > 85) & (temp_f >= 80) & (temp_f <= 87)
    ajuste_alta_humedad = ((rh - 85) / 10) * ((87 - temp_f) / 5)
    hi_rothfusz = np.where(aplica_alta_humedad, hi_rothfusz + ajuste_alta_humedad, hi_rothfusz)

    return np.where(promedio >= 80, hi_rothfusz, hi_simple)


def indice_calor_c(temp_c, rh):
    temp_f = temp_c * 9 / 5 + 32
    return (indice_calor_f(temp_f, rh) - 32) * 5 / 9


def normalizar(serie):
    return (serie - serie.min()) / (serie.max() - serie.min())


# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file("municipios_espana.shp")
# Asegurar que está en coordenadas geográficas estándar (WGS84) para coincidir con Copernicus
municipios_base = municipios_base.to_crs(epsg=4326)

# Código INE de municipio (provincia + municipio) = últimos 5 dígitos del NATCODE del CNIG
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]

# 2. Obtener población por municipio (INE, Padrón - último año disponible). No depende del
# año/escenario climático, así que se calcula una sola vez para toda la matriz.
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

municipios_base['poblacion'] = municipios_base['ine_code'].map(poblacion_por_municipio)
poblacion_log = np.log1p(municipios_base['poblacion'])
poblacion_norm = normalizar(poblacion_log)


def procesar_combinacion(año, escenario):
    municipios = municipios_base.copy()

    # 3. Abrir el NetCDF de temperaturas EURO-CORDEX de esta combinación año/escenario (ya
    # recortado a España). Trae la media de verano de la temperatura máxima y de la mínima,
    # ambas en grados Celsius, a ~11km de resolución, en lat/lon normales.
    ds_temp = xr.open_dataset(f"temperaturas_{año}_{escenario}_eurocordex.nc", engine="netcdf4")
    ds_temp = ds_temp.rio.write_crs("EPSG:4326")
    ds_temp = ds_temp.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)

    # 4. Abrir el NetCDF de humedad relativa (CORDEX crudo, ver README sobre la inconsistencia
    # metodológica de mezclar un único modelo con la media de conjunto de la temperatura).
    # CORDEX usa una malla de "polo rotado" (rlat/rlon), no lat/lon directos, así que hay que
    # reconstruir su proyección a partir de los parámetros guardados en la variable rotated_pole.
    ds_hum = xr.open_dataset(f"humedad_{año}_{escenario}_eurocordex.nc", engine="netcdf4")
    crs_rotado = CRS.from_cf(ds_hum['rotated_pole'].attrs)
    ds_hum = ds_hum.rio.write_crs(crs_rotado)
    ds_hum = ds_hum.rio.set_spatial_dims(x_dim="rlon", y_dim="rlat", inplace=True)
    # Para el punto más cercano en el caso de municipios pequeños, se necesitan sus centroides
    # ya transformados a coordenadas rotadas (rlon/rlat no son lon/lat directos).
    a_rotado = Transformer.from_crs("EPSG:4326", crs_rotado, always_xy=True)

    # 5. Extraer, para cada municipio, la temperatura máxima y mínima media de verano y la
    # humedad relativa media de verano.
    municipios['temp_max_verano_c'] = 0.0
    municipios['temp_min_verano_c'] = 0.0
    municipios['humedad_verano_pct'] = 0.0

    for index, row in municipios.iterrows():
        geom = [row['geometry']]
        centroide = row['geometry'].centroid

        try:
            clip_temp = ds_temp.rio.clip(geom, municipios.crs, drop=True)
            municipios.at[index, 'temp_max_verano_c'] = float(clip_temp['mean_Tmax_Summer'].mean())
            municipios.at[index, 'temp_min_verano_c'] = float(clip_temp['mean_Tmin_Summer'].mean())
        except Exception:
            # Municipios demasiado pequeños para capturar un píxel entero: se usa el valor
            # del punto más cercano.
            cercano = ds_temp.sel(lon=centroide.x, lat=centroide.y, method='nearest')
            municipios.at[index, 'temp_max_verano_c'] = float(cercano['mean_Tmax_Summer'])
            municipios.at[index, 'temp_min_verano_c'] = float(cercano['mean_Tmin_Summer'])

        try:
            clip_hum = ds_hum.rio.clip(geom, municipios.crs, drop=True)
            municipios.at[index, 'humedad_verano_pct'] = float(clip_hum['hurs'].mean())
        except Exception:
            rlon, rlat = a_rotado.transform(centroide.x, centroide.y)
            cercano = ds_hum.sel(rlon=rlon, rlat=rlat, method='nearest')
            municipios.at[index, 'humedad_verano_pct'] = float(cercano['hurs'])

    # 6. Índice de calor (temperatura + humedad) para el día (con temp. máxima) y para la
    # noche (con temp. mínima, ligado a las "noches tropicales"): a igual temperatura, más
    # humedad hace que el calor se sienta -y afecte al cuerpo- más de lo que indica el
    # termómetro.
    municipios['heat_index_max_c'] = indice_calor_c(municipios['temp_max_verano_c'], municipios['humedad_verano_pct'])
    municipios['heat_index_min_c'] = indice_calor_c(municipios['temp_min_verano_c'], municipios['humedad_verano_pct'])

    # 7. Indicador de riesgo de mortalidad por calor (proxy relativo, no una predicción real
    # de muertes). La exposición al calor combina, a partes iguales, el índice de calor
    # diurno y el nocturno (calor + humedad) - las dos variables climáticas pesan 50%/50%
    # entre sí. Esa exposición combinada se pondera después a partes iguales con la
    # población expuesta (en escala logarítmica, muy sesgada: de ~10 a >3M habitantes por
    # municipio, calculada una sola vez para toda la matriz más arriba), para reflejar
    # cuánta gente está realmente afectada.
    heat_index_max_norm = normalizar(municipios['heat_index_max_c'])
    heat_index_min_norm = normalizar(municipios['heat_index_min_c'])
    exposicion_norm = (heat_index_max_norm + heat_index_min_norm) / 2

    municipios['heat_mortality_risk'] = (exposicion_norm + poblacion_norm) / 2

    salida = f"municipios_heatwave_risk_{año}_{escenario}.geojson"
    municipios.to_file(salida, driver="GeoJSON")
    print(f"Zonificación de riesgo de ola de calor finalizada: {salida}")


for escenario in ESCENARIOS:
    for año in AÑOS:
        procesar_combinacion(año, escenario)

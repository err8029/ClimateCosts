import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xarray as xr
import rioxarray # Extensión que permite fusionar xarray con operaciones GIS
from pyproj import CRS, Transformer

INE_TABLA_PADRON = "29005"  # "Cifras oficiales del padrón por municipio" (INE)
INE_TABLA_PROYECCION_PROVINCIAL = "36725"  # Proyección de población por provincias, serie 2026-2041 (INE)

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python heat/2_heatwave_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "heat/input"
OUTPUT_DIR = "heat/output"

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


def normalizar(serie, minimo, maximo):
    return (serie - minimo) / (maximo - minimo)


# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
# Asegurar que está en coordenadas geográficas estándar (WGS84) para coincidir con Copernicus
municipios_base = municipios_base.to_crs(epsg=4326)

# Código INE de municipio (provincia + municipio) = últimos 5 dígitos del NATCODE del CNIG
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]

# 2. Obtener población por municipio (INE, Padrón - último año disponible). No depende del
# año/escenario climático, así que se calcula una sola vez para toda la matriz - su rango de
# normalización ya es "fijo" por construcción, sin necesidad de tratamiento especial.
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

# 3. Proyectar la población de cada municipio a 2030 y 2050. El INE no publica proyecciones
# de población por municipio (solo hasta nivel provincia, y solo hasta 2041 - ver README), así
# que se aplica el factor de crecimiento de cada provincia (INE, tabla 36725) a la población
# actual de cada uno de sus municipios: el 2030 usa el dato real de la propia tabla, y el 2050
# extrapola la misma tasa de crecimiento anualizada observada en 2026-2041, otros 9 años más.
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

municipios_base['codigo_provincia'] = municipios_base['ine_code'].str[:2]
municipios_base['poblacion_2030'] = municipios_base['poblacion'] * municipios_base['codigo_provincia'].map(factor_2030_por_provincia)
municipios_base['poblacion_2050'] = municipios_base['poblacion'] * municipios_base['codigo_provincia'].map(factor_2050_por_provincia)

# Igual que con los índices de calor: rango de normalización fijo (de las poblaciones
# proyectadas a 2030 Y 2050 juntas), para que el crecimiento demográfico entre años también
# quede reflejado en heat_mortality_risk en vez de anularse por la normalización.
poblacion_log_por_año = {
    año: np.log1p(municipios_base[f'poblacion_{año}'])
    for año in AÑOS
}
poblacion_log_global = pd.concat(poblacion_log_por_año.values())
rango_poblacion = (poblacion_log_global.min(), poblacion_log_global.max())


def calcular_indices_climaticos(año, escenario):
    municipios = municipios_base.copy()

    # 4. Abrir el NetCDF de temperaturas EURO-CORDEX de esta combinación año/escenario (ya
    # recortado a España). Trae la media de verano de la temperatura máxima y de la mínima,
    # ambas en grados Celsius, a ~11km de resolución, en lat/lon normales.
    ds_temp = xr.open_dataset(f"{INPUT_DIR}/temperaturas_{año}_{escenario}_eurocordex.nc", engine="netcdf4")
    ds_temp = ds_temp.rio.write_crs("EPSG:4326")
    ds_temp = ds_temp.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)

    # 5. Abrir el NetCDF de humedad relativa (CORDEX crudo, ver README sobre la inconsistencia
    # metodológica de mezclar un único modelo con la media de conjunto de la temperatura).
    # CORDEX usa una malla de "polo rotado" (rlat/rlon), no lat/lon directos, así que hay que
    # reconstruir su proyección a partir de los parámetros guardados en la variable rotated_pole.
    ds_hum = xr.open_dataset(f"{INPUT_DIR}/humedad_{año}_{escenario}_eurocordex.nc", engine="netcdf4")
    crs_rotado = CRS.from_cf(ds_hum['rotated_pole'].attrs)
    ds_hum = ds_hum.rio.write_crs(crs_rotado)
    ds_hum = ds_hum.rio.set_spatial_dims(x_dim="rlon", y_dim="rlat", inplace=True)
    # Para el punto más cercano en el caso de municipios pequeños, se necesitan sus centroides
    # ya transformados a coordenadas rotadas (rlon/rlat no son lon/lat directos).
    a_rotado = Transformer.from_crs("EPSG:4326", crs_rotado, always_xy=True)

    # 6. Extraer, para cada municipio, la temperatura máxima y mínima media de verano y la
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

    # 7. Índice de calor (temperatura + humedad) para el día (con temp. máxima) y para la
    # noche (con temp. mínima, ligado a las "noches tropicales"): a igual temperatura, más
    # humedad hace que el calor se sienta -y afecte al cuerpo- más de lo que indica el
    # termómetro.
    municipios['heat_index_max_c'] = indice_calor_c(municipios['temp_max_verano_c'], municipios['humedad_verano_pct'])
    municipios['heat_index_min_c'] = indice_calor_c(municipios['temp_min_verano_c'], municipios['humedad_verano_pct'])
    return municipios


# 8. Calcular los índices climáticos de las 4 combinaciones ANTES de normalizar nada. Así se
# puede usar un rango de normalización fijo (min/max de las 4 combinaciones juntas) en vez de
# uno por año: si se normaliza cada año por separado, heat_mortality_risk deja de reflejar el
# calentamiento real y pasa a reflejar solo la posición relativa dentro de ese año - un
# municipio puede calentarse en términos absolutos y aun así bajar en el ranking normalizado
# si el extremo superior de la distribución (con datos de un único modelo de humedad, algo
# ruidoso) sube más rápido todavía. Ver README.
resultados = {
    (año, escenario): calcular_indices_climaticos(año, escenario)
    for escenario in ESCENARIOS
    for año in AÑOS
}

heat_index_max_global = pd.concat([r['heat_index_max_c'] for r in resultados.values()])
heat_index_min_global = pd.concat([r['heat_index_min_c'] for r in resultados.values()])
rango_max = (heat_index_max_global.min(), heat_index_max_global.max())
rango_min = (heat_index_min_global.min(), heat_index_min_global.max())

for (año, escenario), municipios in resultados.items():
    # 9. Indicador de riesgo de mortalidad por calor (proxy relativo, no una predicción real de
    # muertes): reparto a partes iguales (33.3% cada una) entre el índice de calor diurno, el
    # nocturno y la población expuesta (proyectada al año correspondiente, en escala
    # logarítmica, muy sesgada: de ~10 a >3M habitantes por municipio). Tanto los índices de
    # calor como la población se normalizan con rangos fijos (calculados arriba, sobre las 4
    # combinaciones juntas, no por año), para que el indicador sí capture el calentamiento y
    # el crecimiento demográfico entre 2030 y 2050 en vez de solo el ranking relativo de cada año.
    heat_index_max_norm = normalizar(municipios['heat_index_max_c'], *rango_max)
    heat_index_min_norm = normalizar(municipios['heat_index_min_c'], *rango_min)
    poblacion_norm = normalizar(poblacion_log_por_año[año], *rango_poblacion)
    municipios['heat_mortality_risk'] = (heat_index_max_norm + heat_index_min_norm + poblacion_norm) / 3
    # La columna 'poblacion' pasa a reflejar la población proyectada usada en ESTE año, no
    # siempre la actual (2025/26).
    municipios['poblacion'] = municipios_base[f'poblacion_{año}']

    salida = f"{OUTPUT_DIR}/municipios_heatwave_risk_{año}_{escenario}.geojson"
    municipios.to_file(salida, driver="GeoJSON")

    # Versión ligera para la app: solo las columnas que se visualizan, sin los campos
    # intermedios (temperaturas/humedad crudas, población, metadatos INSPIRE...). Quitar
    # columnas apenas reduce el peso (la geometría es lo que más pesa), así que además se
    # simplifica la geometría: a un umbral de 0.001° (~111m) el contorno de cada municipio
    # sigue viéndose igual de bien a la escala de un mapa nacional/de ciudad, pero el archivo
    # pesa ~90% menos y la app tarda mucho menos en cargarlo y renderizarlo.
    # ine_code (no solo NAMEUNIT) porque hay 17 nombres de municipio duplicados a nivel
    # nacional (p.ej. "Mieres" existe en dos provincias distintas) - la app lo necesita
    # como clave de cruce fiable entre años.
    columnas_lite = ['NAMEUNIT', 'ine_code', 'heat_mortality_risk', 'heat_index_max_c', 'heat_index_min_c', 'geometry']
    municipios_lite = municipios[columnas_lite].copy()
    municipios_lite['geometry'] = municipios_lite.geometry.simplify(0.001, preserve_topology=True)
    salida_lite = f"{OUTPUT_DIR}/municipios_heatwave_risk_{año}_{escenario}_lite.geojson"
    municipios_lite.to_file(salida_lite, driver="GeoJSON")

    print(f"Zonificación de riesgo de ola de calor finalizada: {salida} / {salida_lite}")

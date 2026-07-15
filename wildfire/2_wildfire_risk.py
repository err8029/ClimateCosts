import glob

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xarray as xr
import rioxarray  # Extensión que permite fusionar xarray con operaciones GIS

INE_TABLA_PADRON = "29005"  # "Cifras oficiales del padrón por municipio" (INE)
INE_TABLA_PROYECCION_PROVINCIAL = "36725"  # Proyección de población por provincias, serie 2026-2041 (INE)

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python wildfire/2_wildfire_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "wildfire/input"
OUTPUT_DIR = "wildfire/output"

# Misma matriz año x escenario que heat/2_heatwave_risk.py.
AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']

# Igual que drought/2_drought_risk.py: los valores anuales son ruidosos (un año concreto es
# "tiempo", no "clima"), así que se usa la media de una ventana climatológica de 20 años
# centrada en cada año objetivo, en vez del valor de un único año suelto.
VENTANA = {2030: (2021, 2040), 2050: (2041, 2060)}


def normalizar(serie, minimo, maximo):
    return (serie - minimo) / (maximo - minimo)


# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios_base = municipios_base.to_crs(epsg=4326)
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]

# 2. Obtener población por municipio (INE, Padrón - último año disponible). Mismo enfoque
# exacto que heat/2_heatwave_risk.py (ver ahí el razonamiento completo).
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

# 3. Proyectar la población de cada municipio a 2030 y 2050 (mismo factor de crecimiento
# provincial que heat/flood/drought - ver heat/2_heatwave_risk.py para el razonamiento).
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

# Rango de normalización fijo de población (log-escala), igual que heat: para que el
# crecimiento demográfico entre 2030 y 2050 se refleje en wildfire_risk en vez de anularse.
poblacion_log_por_año = {
    año: np.log1p(municipios_base[f'poblacion_{año}'])
    for año in AÑOS
}
poblacion_log_global = pd.concat(poblacion_log_por_año.values())
rango_poblacion = (poblacion_log_global.min(), poblacion_log_global.max())


def abrir_variable(escenario, variable):
    carpeta = f"{INPUT_DIR}/wildfire_raw_{escenario}"
    ruta = glob.glob(f"{carpeta}/*{variable}*.nc")[0]
    ds = xr.open_dataset(ruta, engine="netcdf4")
    ds = ds.rio.write_crs("EPSG:4326")
    ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
    return ds


def calcular_indices_climaticos(año, escenario, ds_fwi, ds_dias):
    municipios = municipios_base.copy()

    y0, y1 = VENTANA[año]
    media_fwi = ds_fwi.sel(time=slice(f'{y0}-01-01', f'{y1}-12-31'))['canadian_fire_weather_index'].mean(dim='time')
    media_dias = ds_dias.sel(time=slice(f'{y0}-01-01', f'{y1}-12-31'))['high_fire_danger_days'].mean(dim='time')

    municipios['fire_weather_index'] = np.nan
    municipios['high_fire_danger_days'] = np.nan

    for index, row in municipios.iterrows():
        geom = [row['geometry']]
        centroide = row['geometry'].centroid

        for capa, columna in ((media_fwi, 'fire_weather_index'), (media_dias, 'high_fire_danger_days')):
            # A diferencia de heat/drought (donde el recorte cae fuera de la rejilla y
            # rio.clip() lanza una excepción de forma fiable), esta rejilla tiene celdas NaN
            # dispersas dentro de zonas con tierra (no solo mar): un recorte puede "tener
            # éxito" y aun así devolver solo NaN, sin lanzar ninguna excepción. Por eso aquí
            # se comprueba np.isfinite() explícitamente en vez de fiarse del try/except, y
            # se cae al punto más cercano tanto si el recorte falla como si da NaN.
            valor = np.nan
            try:
                clip = capa.rio.clip(geom, municipios.crs, drop=True)
                valor = float(clip.mean())
            except Exception:
                pass

            if not np.isfinite(valor):
                cercano = capa.sel(lon=centroide.x, lat=centroide.y, method='nearest')
                valor = float(cercano)

            if np.isfinite(valor):
                municipios.at[index, columna] = valor

    return municipios


# 4. Calcular los índices climáticos de las 4 combinaciones ANTES de normalizar nada, igual
# que heat: así se usa un rango de normalización fijo (min/max de las 4 combinaciones juntas)
# en vez de uno por año, para que wildfire_risk refleje el cambio real entre 2030 y 2050 en
# vez de solo el ranking relativo de cada año (ver README, mismo bug que motivó el fix de
# heat_mortality_risk).
resultados = {}
for escenario in ESCENARIOS:
    ds_fwi = abrir_variable(escenario, 'fire_weather_index')
    ds_dias = abrir_variable(escenario, 'days_with_high_fire_danger')
    for año in AÑOS:
        resultados[(año, escenario)] = calcular_indices_climaticos(año, escenario, ds_fwi, ds_dias)

fwi_global = pd.concat([r['fire_weather_index'] for r in resultados.values()])
dias_global = pd.concat([r['high_fire_danger_days'] for r in resultados.values()])
rango_fwi = (fwi_global.min(), fwi_global.max())
rango_dias = (dias_global.min(), dias_global.max())

for (año, escenario), municipios in resultados.items():
    # 5. Indicador de riesgo de incendio forestal (proxy relativo, no una predicción real de
    # incendios): reparto a partes iguales (33.3% cada una) entre el índice de peligro
    # (Canadian FWI), los días/año de peligro alto, y la población expuesta (proyectada al
    # año correspondiente, en escala logarítmica) - misma fórmula exacta que
    # heat_mortality_risk.
    fwi_norm = normalizar(municipios['fire_weather_index'], *rango_fwi)
    dias_norm = normalizar(municipios['high_fire_danger_days'], *rango_dias)
    poblacion_norm = normalizar(poblacion_log_por_año[año], *rango_poblacion)
    municipios['wildfire_risk'] = (fwi_norm + dias_norm + poblacion_norm) / 3
    municipios['poblacion'] = municipios_base[f'poblacion_{año}']

    salida = f"{OUTPUT_DIR}/municipios_wildfire_risk_{año}_{escenario}.geojson"
    municipios.to_file(salida, driver="GeoJSON")

    # Versión ligera para la app, igual que heat/drought: solo las columnas visualizadas, con
    # geometría simplificada. ine_code (no solo NAMEUNIT) porque hay 17 nombres de municipio
    # duplicados a nivel nacional.
    columnas_lite = ['NAMEUNIT', 'ine_code', 'wildfire_risk', 'fire_weather_index', 'high_fire_danger_days', 'geometry']
    municipios_lite = municipios[columnas_lite].copy()
    municipios_lite['geometry'] = municipios_lite.geometry.simplify(0.001, preserve_topology=True)
    salida_lite = f"{OUTPUT_DIR}/municipios_wildfire_risk_{año}_{escenario}_lite.geojson"
    municipios_lite.to_file(salida_lite, driver="GeoJSON")

    print(f"Zonificación de riesgo de incendio forestal finalizada: {salida} / {salida_lite}")

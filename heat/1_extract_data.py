import cdsapi
import glob
import xarray as xr
import zipfile
import os

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python heat/1_extract_data.py
INPUT_DIR = "heat/input"

# Inicializa el cliente de la API (leerá automáticamente tu archivo .cdsapirc)
c = cdsapi.Client()

# Coordenadas [Norte, Oeste, Sur, Este] cubriendo España peninsular y Baleares.
# Canarias queda fuera de esta caja (distinto huso/CRS) y se trata por separado.
area_espana = [44.0, -9.5, 36.0, 4.5]

# Matriz de años x escenarios que la app permite seleccionar. "rcp4_5"/"rcp8_5" es la
# nomenclatura de sis-temperature-statistics; CORDEX usa "rcp_4_5"/"rcp_8_5" (con guion
# bajo distinto), de ahí el diccionario ESCENARIO_CORDEX.
AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']
ESCENARIO_CORDEX = {'rcp4_5': 'rcp_4_5', 'rcp8_5': 'rcp_8_5'}

# DESCARGA PARA MORTALIDAD POR CALOR (Temperaturas máximas y mínimas de verano, EURO-CORDEX)
# El riesgo de inundación y sequía se obtienen de fuentes oficiales (SNCZI, SPEI)
# en lugar de derivarse de la precipitación de CMIP6 (ver README).
#
# Este dataset no admite filtrar por año ni por área en la propia petición: siempre
# devuelve toda Europa (1986-2085) PARA UN ESCENARIO, así que solo hace falta una
# descarga por escenario (no por año): el recorte a España y a cada año se hace
# localmente con xarray después de descargar.
#
# Al pedir dos variables (max y min), la API empaqueta dos NetCDF distintos en un
# .zip (a pesar del nombre de archivo que se le dé a c.retrieve), no un único .nc.


def recorte_espana(ds, año):
    # lat/lon son ascendentes en este dataset: el slice debe ir (sur, norte), no
    # (norte, sur), o xarray devuelve un recorte vacío sin avisar.
    return ds.sel(
        lat=slice(area_espana[2], area_espana[0]),
        lon=slice(area_espana[1], area_espana[3]),
        time=f'{año}-06-01',
    )


for escenario in ESCENARIOS:
    zip_name = f'{INPUT_DIR}/summer_max_min_{escenario}.zip'
    carpeta = f'{INPUT_DIR}/sis_temp_raw_{escenario}'

    if not os.path.exists(carpeta):
        c.retrieve(
            'sis-temperature-statistics',
            {
                'variable': ['maximum_temperature', 'minimum_temperature'],
                'period': 'summer',                     # JJA
                'statistic': ['time_average'],          # or percentiles
                'experiment': [escenario],
                'ensemble_statistic': ['ensemble_members_average'],
            },
            zip_name,
        )
        with zipfile.ZipFile(zip_name) as z:
            z.extractall(carpeta)

    # Cada variable viene en su propio NetCDF dentro del zip, con nombres de variable
    # distintos (mean_Tmax_Summer / mean_Tmin_Summer) y en grados Celsius. El nombre exacto
    # de archivo varía según el escenario, así que se busca por patrón en vez de asumirlo.
    ds_max = xr.open_dataset(glob.glob(f'{carpeta}/mean_Tmax_Summer*.nc')[0])
    ds_min = xr.open_dataset(glob.glob(f'{carpeta}/mean_Tmin_Summer*.nc')[0])

    for año in AÑOS:
        ds_es = xr.merge([recorte_espana(ds_max, año), recorte_espana(ds_min, año)])
        ds_es.to_netcdf(f'{INPUT_DIR}/temperaturas_{año}_{escenario}_eurocordex.nc')

# DESCARGA DE HUMEDAD (para el Índice de Calor, que necesita temperatura + humedad)
#
# No existe un dataset de humedad ya procesado al mismo nivel que sis-temperature-statistics,
# así que aquí se usa CORDEX en crudo: humedad relativa diaria del modelo MOHC-HadGEM2-ES
# regionalizado con SMHI-RCA4 (r1i1p1, dominio EUR-11 ~0.11°). Al ser un único modelo (no una
# media de conjunto como la temperatura), esto introduce una inconsistencia metodológica
# menor entre ambas variables (ver README).
#
# A diferencia de sis-temperature-statistics, aquí SÍ se puede (y hay que) filtrar por año,
# escenario y área directamente en la petición: una descarga por combinación año x escenario.
for escenario in ESCENARIOS:
    for año in AÑOS:
        zip_name = f'{INPUT_DIR}/humedad_{año}_{escenario}.zip'
        carpeta = f'{INPUT_DIR}/cordex_humedad_raw_{año}_{escenario}'
        salida = f'{INPUT_DIR}/humedad_{año}_{escenario}_eurocordex.nc'

        if os.path.exists(salida):
            continue

        c.retrieve(
            'projections-cordex-domains-single-levels',
            {
                'domain': 'europe',
                'experiment': ESCENARIO_CORDEX[escenario],
                'horizontal_resolution': '0_11_degree_x_0_11_degree',
                'temporal_resolution': 'daily_mean',
                'variable': '2m_relative_humidity',
                'gcm_model': 'mohc_hadgem2_es',
                'rcm_model': 'smhi_rca4',
                'ensemble_member': 'r1i1p1',
                'year': [str(año)],
                'month': ['06', '07', '08'],              # JJA, igual que la temperatura
                'area': area_espana,
            },
            zip_name,
        )

        with zipfile.ZipFile(zip_name) as z:
            nombre_nc = [n for n in z.namelist() if n.endswith('.nc')][0]
            z.extract(nombre_nc, carpeta)

        # CORDEX usa una malla de "polo rotado" (rlat/rlon), no lat/lon directos. Se promedia
        # solo la variable de humedad sobre el tiempo, y se conserva rotated_pole (contiene
        # los parámetros del polo, necesarios para reconstruir la proyección) sin tocar -
        # promediarla junto con hurs falla, porque es un campo de texto, no numérico.
        ds_hum = xr.open_dataset(f'{carpeta}/{nombre_nc}')
        humedad_media = ds_hum['hurs'].mean(dim='time', keep_attrs=True)
        xr.Dataset({'hurs': humedad_media, 'rotated_pole': ds_hum['rotated_pole']}).to_netcdf(salida)

print("Descarga completada con éxito.")

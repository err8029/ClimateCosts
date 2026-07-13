import cdsapi
import xarray as xr
import zipfile

# Inicializa el cliente de la API (leerá automáticamente tu archivo .cdsapirc)
c = cdsapi.Client()

# Coordenadas [Norte, Oeste, Sur, Este] cubriendo España peninsular y Baleares.
# Canarias queda fuera de esta caja (distinto huso/CRS) y se trata por separado.
area_espana = [44.0, -9.5, 36.0, 4.5]

# DESCARGA PARA MORTALIDAD POR CALOR (Temperaturas máximas y mínimas de verano, EURO-CORDEX)
# El riesgo de inundación y sequía se obtienen de fuentes oficiales (SNCZI, SPEI)
# en lugar de derivarse de la precipitación de CMIP6 (ver README).
#
# Este dataset no admite filtrar por año ni por área en la propia petición: siempre
# devuelve toda Europa (1986-2085), así que el recorte a España y a 2030 se hace
# localmente con xarray después de descargar.
#
# Al pedir dos variables (max y min), la API empaqueta dos NetCDF distintos en un
# .zip (a pesar del nombre de archivo que se le dé a c.retrieve), no un único .nc.

c.retrieve(
    'sis-temperature-statistics',
    {
        'variable': ['maximum_temperature', 'minimum_temperature'],
        'period': 'summer',                     # JJA
        'statistic': ['time_average'],          # or percentiles
        'experiment': ['rcp4_5'],               # or rcp8_5
        'ensemble_statistic': ['ensemble_members_average'],
    },
    'summer_max_min.zip'
)

with zipfile.ZipFile('summer_max_min.zip') as z:
    z.extractall('sis_temp_raw')

# Cada variable viene en su propio NetCDF dentro del zip, con nombres de variable
# distintos (mean_Tmax_Summer / mean_Tmin_Summer) y en grados Celsius.
ds_max = xr.open_dataset('sis_temp_raw/mean_Tmax_Summer_rcp45_mean_v1.0.nc')
ds_min = xr.open_dataset('sis_temp_raw/mean_Tmin_Summer_rcp45_mean_v1.0.nc')


def recorte_espana_2030(ds):
    # lat/lon son ascendentes en este dataset: el slice debe ir (sur, norte), no
    # (norte, sur), o xarray devuelve un recorte vacío sin avisar.
    return ds.sel(
        lat=slice(area_espana[2], area_espana[0]),
        lon=slice(area_espana[1], area_espana[3]),
        time='2030-06-01',
    )


ds_es = xr.merge([recorte_espana_2030(ds_max), recorte_espana_2030(ds_min)])
ds_es.to_netcdf('temperaturas_2030_eurocordex.nc')

# DESCARGA DE HUMEDAD (para el Índice de Calor, que necesita temperatura + humedad)
#
# No existe un dataset de humedad ya procesado al mismo nivel que sis-temperature-statistics,
# así que aquí se usa CORDEX en crudo: humedad relativa diaria del modelo MOHC-HadGEM2-ES
# regionalizado con SMHI-RCA4 (r1i1p1, RCP4.5, dominio EUR-11 ~0.11°), el mismo escenario de
# emisiones que la temperatura. Al ser un único modelo (no una media de conjunto como la
# temperatura), esto introduce una inconsistencia metodológica menor entre ambas variables
# (ver README).
#
# A diferencia de sis-temperature-statistics, aquí SÍ se puede filtrar por año, mes y área
# directamente en la petición.
c.retrieve(
    'projections-cordex-domains-single-levels',
    {
        'domain': 'europe',
        'experiment': 'rcp_4_5',
        'horizontal_resolution': '0_11_degree_x_0_11_degree',
        'temporal_resolution': 'daily_mean',
        'variable': '2m_relative_humidity',
        'gcm_model': 'mohc_hadgem2_es',
        'rcm_model': 'smhi_rca4',
        'ensemble_member': 'r1i1p1',
        'year': ['2030'],
        'month': ['06', '07', '08'],              # JJA, igual que la temperatura
        'area': area_espana,
    },
    'humedad_2030.zip'
)

with zipfile.ZipFile('humedad_2030.zip') as z:
    nombre_nc = [n for n in z.namelist() if n.endswith('.nc')][0]
    z.extract(nombre_nc, 'cordex_humedad_raw')

# CORDEX usa una malla de "polo rotado" (rlat/rlon), no lat/lon directos. Se promedia solo
# la variable de humedad sobre el tiempo, y se conserva rotated_pole (contiene los
# parámetros del polo, necesarios para reconstruir la proyección) sin tocar - promediarla
# junto con hurs falla, porque es un campo de texto, no numérico.
ds_hum = xr.open_dataset(f'cordex_humedad_raw/{nombre_nc}')
humedad_media = ds_hum['hurs'].mean(dim='time', keep_attrs=True)
humedad_verano_2030 = xr.Dataset({'hurs': humedad_media, 'rotated_pole': ds_hum['rotated_pole']})
humedad_verano_2030.to_netcdf('humedad_2030_eurocordex.nc')

print("Descarga completada con éxito.")

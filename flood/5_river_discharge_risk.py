import glob

import geopandas as gpd
import numpy as np
import xarray as xr
import rioxarray  # Extensión que permite fusionar xarray con operaciones GIS

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python flood/5_river_discharge_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "flood/input"
OUTPUT_DIR = "flood/output"

ESCENARIOS = ['rcp4_5', 'rcp8_5']
PERIODOS_RETORNO = {'1_in_2_year': '2y', '1_in_5_year': '5y', '1_in_10_year': '10y', '1_in_50_year': '50y'}

# El dataset ya viene como 3 ventanas climatológicas fijas de 30 años (índices de tiempo
# 0/1/2, ver flood/4_extract_discharge_data.py): se usan las dos primeras (más cercanas al
# presente y a medio siglo) para mantener el mismo patrón de "dos periodos comparables" que
# el resto de la app, en vez de forzar una etiqueta "2030"/"2050" que no correspondería a
# los años reales de estas ventanas.
EPOCAS = {'2011_2040': 0, '2041_2070': 1}

# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios_base = municipios_base.to_crs(epsg=4326)
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]


def abrir_variable(periodo_retorno, escenario):
    carpeta = f"{INPUT_DIR}/discharge_raw_{periodo_retorno}_{escenario}"
    ruta = glob.glob(f"{carpeta}/*.nc")[0]
    ds = xr.open_dataset(ruta, engine="netcdf4")
    ds = ds.rio.write_crs("EPSG:4326")
    ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
    return ds


for escenario in ESCENARIOS:
    # 2. Abrir los 4 periodos de retorno de este escenario (cada uno ya trae las 3 ventanas
    # climatológicas en su dimensión de tiempo).
    datasets = {periodo: abrir_variable(periodo, escenario) for periodo in PERIODOS_RETORNO}

    for epoca, indice_tiempo in EPOCAS.items():
        municipios = municipios_base.copy()

        columnas = {periodo: f'river_discharge_{sufijo}' for periodo, sufijo in PERIODOS_RETORNO.items()}
        for columna in columnas.values():
            municipios[columna] = np.nan

        # 3. Extraer, para cada municipio, el caudal MÁXIMO dentro de su geometría (no la
        # media): el caudal solo es significativo en las celdas que caen sobre un cauce, así
        # que promediar con las celdas sin cauce (NaN, ~36% de la rejilla en España)
        # diluiría el indicador. El máximo refleja el curso de agua más caudaloso que pasa
        # por el municipio, que es lo relevante para el riesgo de crecida.
        for periodo, columna in columnas.items():
            capa = datasets[periodo].isel(time=indice_tiempo)['flood_recurrence']

            for index, row in municipios.iterrows():
                geom = [row['geometry']]
                centroide = row['geometry'].centroid

                try:
                    clip = capa.rio.clip(geom, municipios.crs, drop=True)
                    valor = float(clip.max())
                    if np.isfinite(valor):
                        municipios.at[index, columna] = valor
                except Exception:
                    pass

                if not np.isfinite(municipios.at[index, columna]):
                    # Sin cauce dentro del municipio: se prueba el punto más cercano: si
                    # también es NaN (municipio lejos de cualquier cauce significativo a
                    # esta resolución), se deja el valor nulo - no se rellena con 0, para no
                    # confundir "sin dato" con "caudal cero" (ver Known limitations, README).
                    cercano = capa.sel(lon=centroide.x, lat=centroide.y, method='nearest')
                    valor_cercano = float(cercano)
                    if np.isfinite(valor_cercano):
                        municipios.at[index, columna] = valor_cercano

        salida = f"{OUTPUT_DIR}/municipios_river_discharge_{epoca}_{escenario}.geojson"
        municipios.to_file(salida, driver="GeoJSON")

        columnas_lite = ['NAMEUNIT', 'ine_code'] + list(columnas.values()) + ['geometry']
        municipios_lite = municipios[columnas_lite].copy()
        municipios_lite['geometry'] = municipios_lite.geometry.simplify(0.001, preserve_topology=True)
        salida_lite = f"{OUTPUT_DIR}/municipios_river_discharge_{epoca}_{escenario}_lite.geojson"
        municipios_lite.to_file(salida_lite, driver="GeoJSON")

        print(f"Zonificación de caudal fluvial finalizada: {salida} / {salida_lite}")

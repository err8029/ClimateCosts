import glob

import geopandas as gpd
import xarray as xr
import rioxarray  # Extensión que permite fusionar xarray con operaciones GIS

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python drought/2_drought_risk.py
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "drought/input"
OUTPUT_DIR = "drought/output"

# Misma matriz año x escenario que heat/2_heatwave_risk.py.
AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']

# Los valores anuales del dataset son ruidosos (un año concreto es "tiempo", no "clima": ver
# README): se usa la media de una ventana climatológica de 20 años centrada en cada año
# objetivo, en vez del valor de un único año suelto.
VENTANA = {2030: (2021, 2040), 2050: (2041, 2060)}

# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios_base = municipios_base.to_crs(epsg=4326)
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]


def abrir_variable(escenario, variable):
    carpeta = f"{INPUT_DIR}/drought_raw_{escenario}"
    ruta = glob.glob(f"{carpeta}/*{variable}*.nc")[0]
    ds = xr.open_dataset(ruta, engine="netcdf4")
    ds = ds.rio.write_crs("EPSG:4326")
    ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
    return ds


for escenario in ESCENARIOS:
    # 2. Abrir las dos variables de este escenario (ya cubren todo el periodo 1970-2098: no
    # hace falta volver a abrir el archivo por año, solo recortar la ventana temporal).
    ds_duracion = abrir_variable(escenario, 'duration_of_meteorological_droughts')
    ds_magnitud = abrir_variable(escenario, 'magnitude_of_meteorological_droughts')

    for año in AÑOS:
        municipios = municipios_base.copy()

        y0, y1 = VENTANA[año]
        media_duracion = ds_duracion.sel(time=slice(f'{y0}-01-01', f'{y1}-12-31'))['meteorological_droughts_duration'].mean(dim='time')
        media_magnitud = ds_magnitud.sel(time=slice(f'{y0}-01-01', f'{y1}-12-31'))['meteorological_droughts_magnitude'].mean(dim='time')

        # 3. Extraer, para cada municipio, la media de ambas variables sobre la ventana. La
        # rejilla es de 0.25° (~25km): mucho más gruesa que los ~11km de la temperatura de
        # heat, así que muchos más municipios (sobre todo los pequeños) caen en el
        # "punto más cercano" en vez de un recorte real - ver Known Limitations en el README.
        municipios['drought_duration_months'] = 0.0
        municipios['drought_magnitude'] = 0.0

        for index, row in municipios.iterrows():
            geom = [row['geometry']]
            centroide = row['geometry'].centroid

            try:
                clip_dur = media_duracion.rio.clip(geom, municipios.crs, drop=True)
                municipios.at[index, 'drought_duration_months'] = float(clip_dur.mean())
            except Exception:
                cercano = media_duracion.sel(lon=centroide.x, lat=centroide.y, method='nearest')
                municipios.at[index, 'drought_duration_months'] = float(cercano)

            try:
                clip_mag = media_magnitud.rio.clip(geom, municipios.crs, drop=True)
                municipios.at[index, 'drought_magnitude'] = float(clip_mag.mean())
            except Exception:
                cercano = media_magnitud.sel(lon=centroide.x, lat=centroide.y, method='nearest')
                municipios.at[index, 'drought_magnitude'] = float(cercano)

        salida = f"{OUTPUT_DIR}/municipios_drought_risk_{año}_{escenario}.geojson"
        municipios.to_file(salida, driver="GeoJSON")

        # Versión ligera para la app, igual que en heat/flood: solo las columnas visualizadas,
        # con la geometría simplificada.
        columnas_lite = ['NAMEUNIT', 'ine_code', 'drought_duration_months', 'drought_magnitude', 'geometry']
        municipios_lite = municipios[columnas_lite].copy()
        municipios_lite['geometry'] = municipios_lite.geometry.simplify(0.001, preserve_topology=True)
        salida_lite = f"{OUTPUT_DIR}/municipios_drought_risk_{año}_{escenario}_lite.geojson"
        municipios_lite.to_file(salida_lite, driver="GeoJSON")

        print(f"Zonificación de riesgo de sequía finalizada: {salida} / {salida_lite}")

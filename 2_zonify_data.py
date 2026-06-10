import geopandas as gpd
import xarray as xr
import rioxarray # Extensión que permite fusionar xarray con operaciones GIS

# 1. Cargar el mapa de municipios en formato GeoJSON o Shapefile
municipios = gpd.read_file("municipios_comunidad.shp")
# Asegurar que está en coordenadas geográficas estándar (WGS84) para coincidir con Copernicus
municipios = municipios.to_crs(epsg=4326)

# 2. Abrir el archivo NetCDF de temperaturas descargado en el Paso 1
ds = xr.open_dataset("temperaturas_2030.nc", engine="netcdf4")


# Configurar el NetCDF para que reconozca las dimensiones espaciales como coordenadas GIS
ds = ds.rio.write_crs("EPSG:4326")
ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)

# 3. Extraer el valor medio de temperatura o precipitación para cada municipio
# Creamos columnas nuevas en nuestro mapa de municipios para guardar los indicadores climáticos del 2030
municipios['temp_max_verano'] = 0.0
municipios['precip_max_24h'] = 0.0

for index, row in municipios.iterrows():
    # Crear la geometría del municipio actual
    geom = [row['geometry']]
    
    try:
        # Recortar el raster de Copernicus usando la forma exacta del municipio
        municipio_clip = ds.rio.clip(geom, municipios.crs, drop=True)
        
        # Calcular el indicador climático necesario para el escenario 2030
        # Ejemplo: Promedio de las temperaturas máximas del verano en ese municipio
        municipios.at[index, 'temp_max_verano'] = float(municipio_clip['tasmax'].mean())
        
    except Exception as e:
        # En caso de municipios excesivamente pequeños que no capturen un píxel entero,
        # se les asigna el valor del punto más cercano
        municipios.at[index, 'temp_max_verano'] = float(ds['tasmax'].sel(lon=row['geometry'].centroid.x, lat=row['geometry'].centroid.y, method='nearest').mean())

# Guardar el mapa resultante listo para procesar costes
municipios.to_file("municipios_con_clima_2030.geojson", driver="GeoJSON")
print("Zonificación climática finalizada.")

import cdsapi

# Inicializa el cliente de la API (leerá automáticamente tu archivo .cdsapirc)
c = cdsapi.Client()

# Definir las coordenadas aproximadas de tu Comunidad Autónoma [Norte, Oeste, Sur, Este]
# Ejemplo para Madrid (puedes ajustarlo exactamente a tu región):
area_comunidad = [41.2, -4.6, 39.8, -3.0] 

# 1. DESCARGA PARA MORTALIDAD (Temperaturas máximas en 2030)
c.retrieve(
    'projections-cmip6',
    {
        'format': 'zip',                        # Se descargará comprimido
        'temporal_resolution': 'daily',         # Datos diarios para detectar olas de calor
        'experiment': 'ssp2_4_5',               # Escenario de emisiones medio
        'variable': 'daily_maximum_near_surface_air_temperature', # Temp Máxima
        'model': 'gfdl_esm4',                   # Puedes elegir este o un promedio multimodelo
        'year': '2030',
        'month': [
            '06', '07', '08', '09'              # Meses de verano en España (riesgo de calor)
        ],
        'area': area_comunidad,                 # Recorte geográfico para tu comunidad
    },
    'temperaturas_2030.zip'                     # Nombre del archivo de salida
)

# 2. DESCARGA PARA INUNDACIONES (Precipitaciones extremas en 2030)
c.retrieve(
    'projections-cmip6',
    {
        'format': 'zip',
        'temporal_resolution': 'daily',         # Para evaluar litros por metro cuadrado en 24h
        'experiment': 'ssp2_4_5',
        'variable': 'precipitation',            # Precipitación acumulada diaria
        'model': 'gfdl_esm4',
        'year': '2030',
        'month': [
            '01', '02', '03', '04', '05', '06',
            '07', '08', '09', '10', '11', '12'  # Año completo para buscar DANAs o borrascas
        ],
        'area': area_comunidad,
    },
    'precipitaciones_2030.zip'
)

print("Descargas completadas con éxito.")

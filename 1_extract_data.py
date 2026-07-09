import cdsapi

# Inicializa el cliente de la API (leerá automáticamente tu archivo .cdsapirc)
c = cdsapi.Client()

# Coordenadas [Norte, Oeste, Sur, Este] cubriendo España peninsular y Baleares.
# Canarias queda fuera de esta caja (distinto huso/CRS) y se trata por separado.
area_espana = [44.0, -9.5, 36.0, 4.5]

# DESCARGA PARA MORTALIDAD POR CALOR (Temperaturas máximas en 2030)
# El riesgo de inundación y sequía se obtienen de fuentes oficiales (SNCZI, SPEI)
# en lugar de derivarse de la precipitación de CMIP6 (ver README).
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
        'area': area_espana,                    # Recorte geográfico: España peninsular + Baleares
    },
    'temperaturas_2030.zip'                     # Nombre del archivo de salida
)

print("Descarga completada con éxito.")

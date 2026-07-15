import cdsapi
import glob
import os
import zipfile

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python wildfire/1_extract_data.py
INPUT_DIR = "wildfire/input"

c = cdsapi.Client()

# "fire_weather_index" (Índice Canadiense de Peligro de Incendio Forestal) y
# "days_with_high_fire_danger" (días/año con peligro alto), del mismo dataset
# sis-ecde-climate-indicators que drought/ y flood/ (caudal). A diferencia de
# flood_recurrence (3 ventanas fijas), esto viene como serie anual igual que drought: hace
# falta promediar una ventana climatológica nosotros mismos (ver wildfire/2_wildfire_risk.py).
#
# Este dataset concreto no usa rcm/ensemble_member (a diferencia de drought/flood): solo
# gcm + experiment. hadgem2_es, mismo modelo que el resto del proyecto por consistencia.
ESCENARIOS = ['rcp4_5', 'rcp8_5']
GCM = 'hadgem2_es'

for escenario in ESCENARIOS:
    carpeta = f'{INPUT_DIR}/wildfire_raw_{escenario}'
    zip_name = f'{INPUT_DIR}/wildfire_{escenario}.zip'

    if os.path.exists(carpeta):
        continue

    c.retrieve(
        'sis-ecde-climate-indicators',
        {
            'variable': ['fire_weather_index', 'days_with_high_fire_danger'],
            'origin': 'projections',
            'experiment': [escenario],
            'gcm': [GCM],
            'temporal_aggregation': ['yearly'],
            'spatial_aggregation': 'gridded',
            'version': 'v2_0',
        },
        zip_name,
    )
    with zipfile.ZipFile(zip_name) as z:
        z.extractall(carpeta)

print("Descarga completada con éxito.")

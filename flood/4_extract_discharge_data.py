import cdsapi
import glob
import os
import zipfile

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python flood/4_extract_discharge_data.py
INPUT_DIR = "flood/input"

c = cdsapi.Client()

# "flood_recurrence" (sis-ecde-climate-indicators, el mismo dataset que drought/): caudal
# fluvial (m3/s) esperado para un periodo de retorno dado, modelado con dos modelos
# hidrológicos (E-HYPE, VIC-WUR) forzados con CORDEX bias-corregido. A diferencia de las
# zonas de riesgo SNCZI/MITECO (población en zona fija de inundación, sin proyección de
# futuro posible), esto SÍ tiene escenarios RCP - pero mide una cosa distinta (intensidad
# del caudal, no población afectada): se trata como un indicador complementario, no un
# sustituto. Ver README.
#
# Ya viene como 3 ventanas climatológicas fijas de 30 años (~2011-2040, ~2041-2070,
# ~2071-2100), no como serie anual: no hace falta promediar ventanas nosotros mismos como en
# drought/.
PERIODOS_RETORNO = ['1_in_2_year', '1_in_5_year', '1_in_10_year', '1_in_50_year']
ESCENARIOS = ['rcp4_5', 'rcp8_5']
GCM, RCM, ENSEMBLE = 'hadgem2_es', 'rca4', 'r1i1p1'

for escenario in ESCENARIOS:
    for periodo in PERIODOS_RETORNO:
        carpeta = f'{INPUT_DIR}/discharge_raw_{periodo}_{escenario}'
        zip_name = f'{INPUT_DIR}/discharge_{periodo}_{escenario}.zip'

        if os.path.exists(carpeta):
            continue

        c.retrieve(
            'sis-ecde-climate-indicators',
            {
                'variable': ['flood_recurrence'],
                'origin': 'projections',
                'experiment': [escenario],
                'gcm': [GCM],
                'rcm': [RCM],
                'ensemble_member': [ENSEMBLE],
                'hydrological_model': ['combined_e_hype_and_vic_wur'],
                'other_parameters': [periodo],
                'temporal_aggregation': ['yearly'],
                'spatial_aggregation': 'gridded',
                'version': 'v2_0',
            },
            zip_name,
        )
        with zipfile.ZipFile(zip_name) as z:
            z.extractall(carpeta)

print("Descarga completada con éxito.")

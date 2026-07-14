import cdsapi
import glob
import os
import zipfile

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python drought/1_extract_data.py
INPUT_DIR = "drought/input"

c = cdsapi.Client()

# "Duración" (meses/año en sequía) y "magnitud" (severidad, índice SPI-3) de sequía
# meteorológica, del dataset oficial sis-ecde-climate-indicators (Copernicus/EEA), derivado
# de CORDEX bias-corregido. A diferencia de SPEIbase (CSIC) -que es solo histórico y está
# detrás de una protección anti-bot que impide la descarga por script- este dataset SÍ cubre
# 1970-2098 bajo escenarios RCP, así que permite proyectar a 2030/2050 igual que el calor.
# Es SPI-3 (solo precipitación), no SPEI (precipitación - evapotranspiración): ver README.
#
# gcm/rcm/ensemble_member no son libres: solo existen combinaciones concretas ya
# regionalizadas. Se usa hadgem2_es/rca4/r1i1p1 (misma familia de modelo que la humedad de
# heat/1_extract_data.py, por consistencia). Descubierto consultando el endpoint de
# "constraints" de la propia API (no está documentado en la web de CDS de forma legible).
ESCENARIOS = ['rcp4_5', 'rcp8_5']
GCM, RCM, ENSEMBLE = 'hadgem2_es', 'rca4', 'r1i1p1'

for escenario in ESCENARIOS:
    zip_name = f'{INPUT_DIR}/drought_{escenario}.zip'
    carpeta = f'{INPUT_DIR}/drought_raw_{escenario}'

    if os.path.exists(carpeta):
        continue

    c.retrieve(
        'sis-ecde-climate-indicators',
        {
            'variable': ['duration_of_meteorological_droughts', 'magnitude_of_meteorological_droughts'],
            'origin': 'projections',
            'experiment': [escenario],
            'gcm': [GCM],
            'rcm': [RCM],
            'ensemble_member': [ENSEMBLE],
            'temporal_aggregation': ['yearly'],
            'spatial_aggregation': 'gridded',
            'version': 'v2_0',
        },
        zip_name,
    )
    with zipfile.ZipFile(zip_name) as z:
        z.extractall(carpeta)

print("Descarga completada con éxito.")

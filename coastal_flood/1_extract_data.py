import cdsapi
import os
import zipfile

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python coastal_flood/1_extract_data.py
INPUT_DIR = "coastal_flood/input"

c = cdsapi.Client()

# "relative_sea_level_rise" (sis-ecde-climate-indicators, el mismo dataset que
# drought/flood-caudal/wildfire): nivel medio del mar anual (m), modelo GTSMv3, en
# ~1.300 estaciones/puntos a lo largo de la costa española (no una rejilla regular como el
# resto de indicadores - ver coastal_flood/2_coastal_flood_risk.py). A diferencia del resto
# de hazards, este indicador SOLO existe bajo el escenario SSP5-8.5 (nomenclatura CMIP6) -
# no hay un equivalente a RCP4.5 en este dataset, así que no hay selector de escenario en
# la página. Cubre hasta 2050 con resolución anual, sin necesidad de elegir GCM/RCM.
ESCENARIO = 'ssp5_8_5'

zip_name = f'{INPUT_DIR}/coastal_flood_{ESCENARIO}.zip'
carpeta = f'{INPUT_DIR}/coastal_flood_raw_{ESCENARIO}'

if not os.path.exists(carpeta):
    c.retrieve(
        'sis-ecde-climate-indicators',
        {
            'variable': ['relative_sea_level_rise'],
            'origin': 'projections',
            'experiment': [ESCENARIO],
            'temporal_aggregation': ['yearly'],
            'spatial_aggregation': 'gridded',
            'version': 'v2_0',
        },
        zip_name,
    )
    with zipfile.ZipFile(zip_name) as z:
        z.extractall(carpeta)

print("Descarga completada con éxito.")

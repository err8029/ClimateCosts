import cdsapi
import os
import zipfile

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python electricity/1_extract_data.py
INPUT_DIR = "electricity/input"

c = cdsapi.Client()

# sis-energy-derived-projections (C3S Energy, distinto del dataset sis-ecde-climate-
# indicators usado por el resto de hazards): demanda eléctrica e hidráulica en MWh/año a
# nivel de PAÍS (no hay desglose municipal - España tiene un único mercado eléctrico
# mayorista, MIBEL, así que este indicador es nacional, no un mapa - ver
# electricity/2_electricity_cost.py y pages/electricity_cost.py).
#
# hadgem2_es/rca4, mismo modelo que el resto del proyecto por consistencia. Cubre
# 1970-2098 con resolución anual - se usa la misma ventana climatológica de 20 años que
# drought/wildfire para suavizar el ruido interanual.
ESCENARIOS = ['rcp_4_5', 'rcp_8_5']
GCM, RCM = 'hadgem2_es', 'rca4'

# La demanda y la hidráulica se piden en energía (MWh); solar y eólica solo están
# disponibles como factor de capacidad (0-1) a nivel de país para esta combinación de
# modelos - se convierten a MWh en el script de riesgo usando la potencia instalada actual
# de España (mantenida constante, ver 2_electricity_cost.py).
VARIABLES_ENERGIA = ['electricity_demand', 'hydro_power_generation_reservoirs', 'hydro_power_generation_rivers']
VARIABLES_FACTOR_CAPACIDAD = ['solar_photovoltaic_power_generation', 'wind_power_generation_onshore']

for escenario in ESCENARIOS:
    for grupo, variables, tipo in [
        ('energia', VARIABLES_ENERGIA, 'energy'),
        ('factor_capacidad', VARIABLES_FACTOR_CAPACIDAD, 'capacity_factor_ratio'),
    ]:
        carpeta = f'{INPUT_DIR}/electricity_raw_{grupo}_{escenario}'
        zip_name = f'{INPUT_DIR}/electricity_{grupo}_{escenario}.zip'

        if os.path.exists(carpeta):
            continue

        c.retrieve(
            'sis-energy-derived-projections',
            {
                'variable': variables,
                'spatial_aggregation': 'country_level',
                'energy_product_type': [tipo],
                'temporal_aggregation': 'annual',
                'experiment': [escenario],
                'rcm': RCM,
                'gcm': [GCM],
            },
            zip_name,
        )
        with zipfile.ZipFile(zip_name) as z:
            z.extractall(carpeta)

print("Descarga completada con éxito.")

import geopandas as gpd
import pandas as pd

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python combined/1_combined_risk.py
#
# Combina los 4 riesgos (calor, inundación, sequía, incendio) a partes iguales (25% cada
# uno) en un único indicador combined_risk por municipio/año/escenario. Cada hazard aporta
# UNA variable representativa, normalizada 0-1 con un rango propio y fijo calculado aquí
# mismo (no reutiliza directamente los rangos de normalización de heat_mortality_risk/
# wildfire_risk, aunque ya sean 0-1, para que los 4 componentes queden en un espacio de
# normalización autocontenido y coherente entre sí - decisión explícita del usuario).
BOUNDARIES_DIR = "shared/boundaries"
OUTPUT_DIR = "combined/output"

AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']


def normalizar(serie, minimo, maximo):
    return (serie - minimo) / (maximo - minimo)


# 1. Cargar el mapa de municipios de toda España (CNIG - líneas límite municipales)
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios_base = municipios_base.to_crs(epsg=4326)
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]

# 2. Inundación: MITECO no tiene escenarios RCP (las zonas de riesgo son geografía fija),
# así que la "aportación" de inundación al combinado varía solo por año, no por escenario -
# se usa la población afectada proyectada a T=100 años (no la fracción flood_risk_t100, que
# no cambia entre 2030 y 2050): así el combinado sí refleja el crecimiento demográfico en
# zona de riesgo, igual que hace population dentro de heat_mortality_risk/wildfire_risk.
inundacion = gpd.read_file("flood/output/municipios_inundacion.geojson")[
    ['ine_code', 'flood_risk_t100_poblacion_afectada_2030', 'flood_risk_t100_poblacion_afectada_2050']
]

# 3. Cargar los 4 combos (año x escenario) de calor, sequía e incendio, y unir con
# inundación (que solo depende del año). calor_norm e incendio_norm se reutilizan tal cual
# (heat_mortality_risk y wildfire_risk ya son composites 0-1 por construcción); inundación y
# sequía necesitan normalización propia porque parten de variables sin escala 0-1.
resultados = {}
for escenario in ESCENARIOS:
    for año in AÑOS:
        calor = gpd.read_file(f"heat/output/municipios_heatwave_risk_{año}_{escenario}.geojson")[
            ['ine_code', 'heat_mortality_risk']
        ]
        sequia = gpd.read_file(f"drought/output/municipios_drought_risk_{año}_{escenario}.geojson")[
            ['ine_code', 'drought_duration_months', 'drought_magnitude']
        ]
        incendio = gpd.read_file(f"wildfire/output/municipios_wildfire_risk_{año}_{escenario}.geojson")[
            ['ine_code', 'wildfire_risk']
        ]

        tabla = municipios_base.merge(calor, on='ine_code', how='left')
        tabla = tabla.merge(inundacion, on='ine_code', how='left')
        tabla = tabla.merge(sequia, on='ine_code', how='left')
        tabla = tabla.merge(incendio, on='ine_code', how='left')
        tabla['inundacion_afectados'] = tabla[f'flood_risk_t100_poblacion_afectada_{año}']

        resultados[(año, escenario)] = tabla

# 4. Rango de normalización fijo (calculado una vez sobre las 4 combinaciones juntas, igual
# que heat_mortality_risk/wildfire_risk/drought_*) para inundación y sequía.
inundacion_global = pd.concat([r['inundacion_afectados'] for r in resultados.values()])
duracion_global = pd.concat([r['drought_duration_months'] for r in resultados.values()])
magnitud_global = pd.concat([r['drought_magnitude'] for r in resultados.values()])
rango_inundacion = (inundacion_global.min(), inundacion_global.max())
rango_duracion = (duracion_global.min(), duracion_global.max())
rango_magnitud = (magnitud_global.min(), magnitud_global.max())

for (año, escenario), tabla in resultados.items():
    tabla['calor_norm'] = tabla['heat_mortality_risk']
    tabla['inundacion_norm'] = normalizar(tabla['inundacion_afectados'], *rango_inundacion)
    tabla['sequia_norm'] = (
        normalizar(tabla['drought_duration_months'], *rango_duracion)
        + normalizar(tabla['drought_magnitude'], *rango_magnitud)
    ) / 2
    tabla['incendio_norm'] = tabla['wildfire_risk']

    componentes = ['calor_norm', 'inundacion_norm', 'sequia_norm', 'incendio_norm']
    # Solo se calcula combined_risk donde los 4 componentes tienen dato: promediar solo
    # los disponibles daría una falsa sensación de "25% cada uno" cuando en realidad
    # faltaría alguno (ver Known limitations, README).
    tabla['combined_risk'] = tabla[componentes].mean(axis=1, skipna=False)

    salida = f"{OUTPUT_DIR}/municipios_combined_risk_{año}_{escenario}.geojson"
    tabla.to_file(salida, driver="GeoJSON")

    columnas_lite = ['NAMEUNIT', 'ine_code', 'combined_risk'] + componentes + ['geometry']
    tabla_lite = tabla[columnas_lite].copy()
    tabla_lite['geometry'] = tabla_lite.geometry.simplify(0.001, preserve_topology=True)
    salida_lite = f"{OUTPUT_DIR}/municipios_combined_risk_{año}_{escenario}_lite.geojson"
    tabla_lite.to_file(salida_lite, driver="GeoJSON")

    print(f"Riesgo combinado finalizado: {salida} / {salida_lite}")

import geopandas as gpd
import pandas as pd

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python combined/1_combined_risk.py
#
# Combina los 4 riesgos (calor, inundación, sequía, incendio) en un único indicador
# combined_risk por municipio/año/escenario. Cada hazard aporta UNA variable representativa,
# normalizada 0-1 con un rango propio y fijo calculado aquí mismo (no reutiliza directamente
# los rangos de normalización de heat_mortality_risk/wildfire_risk, aunque ya sean 0-1, para
# que los 4 componentes queden en un espacio de normalización autocontenido y coherente
# entre sí - decisión explícita del usuario).
#
# Los pesos (40% calor / 30% inundación / 15% sequía / 15% incendio) son los mismos, y por
# el mismo motivo, que los usados para financial_impact_eur (ver 2_financial_impact.py):
# combined_risk YA es esa media ponderada, así que financial_impact_eur simplemente la
# reutiliza (valor_economico_eur x combined_risk) en vez de recalcularla por su cuenta - una
# sola fuente de verdad para los pesos. Es una SUMA ponderada (no un producto): que un
# componente sea 0 (o falte) no anula el resto, solo reduce su parte proporcional.
BOUNDARIES_DIR = "shared/boundaries"
OUTPUT_DIR = "combined/output"

AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']

# Ver README, sección "Financial impact proxy" para las fuentes (JRC PESETA IV, pérdidas
# agregadas EM-DAT/Banco de España-Mannheim) y las limitaciones de estos pesos.
PESOS_HAZARD = {
    'calor_norm': 0.40,
    'inundacion_norm': 0.30,
    'sequia_norm': 0.15,
    'incendio_norm': 0.15,
}


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

    componentes = list(PESOS_HAZARD.keys())
    # Suma ponderada, no un producto: que un componente sea 0 no anula el resto. Si a un
    # municipio le falta ALGÚN componente (el caso más común: el hueco costero de
    # wildfire_risk, ver su página), se recalculan los pesos SOLO entre los componentes
    # disponibles para que sigan sumando 1, en vez de dejar combined_risk en blanco - así
    # un municipio con 3 de 4 componentes sigue teniendo un riesgo combinado, no un hueco.
    # Solo queda nulo si le faltan los 4 (no debería ocurrir en la práctica).
    valores = tabla[componentes]
    pesos = pd.Series(PESOS_HAZARD)
    pesos_disponibles = valores.notna().mul(pesos, axis=1)
    suma_pesos_disponibles = pesos_disponibles.sum(axis=1)
    tabla['combined_risk'] = valores.fillna(0).mul(pesos, axis=1).sum(axis=1) / suma_pesos_disponibles

    salida = f"{OUTPUT_DIR}/municipios_combined_risk_{año}_{escenario}.geojson"
    tabla.to_file(salida, driver="GeoJSON")

    columnas_lite = ['NAMEUNIT', 'ine_code', 'combined_risk'] + componentes + ['geometry']
    tabla_lite = tabla[columnas_lite].copy()
    tabla_lite['geometry'] = tabla_lite.geometry.simplify(0.001, preserve_topology=True)
    salida_lite = f"{OUTPUT_DIR}/municipios_combined_risk_{año}_{escenario}_lite.geojson"
    tabla_lite.to_file(salida_lite, driver="GeoJSON")

    print(f"Riesgo combinado finalizado: {salida} / {salida_lite}")

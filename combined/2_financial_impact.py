import geopandas as gpd
import pandas as pd
import requests

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python combined/2_financial_impact.py
#
# Traduce combined_risk (ver 1_combined_risk.py) a un proxy de impacto económico en euros:
#
#   financial_impact_eur = valor_economico_expuesto(año) x combined_risk
#
# combined_risk YA es la media ponderada por hazard (40% calor / 30% inundación / 15%
# sequía / 15% incendio - ver 1_combined_risk.py, una sola fuente de verdad para esos
# pesos), así que aquí simplemente se reutiliza en vez de recalcularla.
#
# valor_economico_expuesto = población proyectada del municipio x PIB per cápita de su
# provincia (Contabilidad Regional de España, INE tabla 76926) - mismo patrón de
# extrapolación provincia->municipio que la población (INE no publica PIB municipal). El
# PIB per cápita se mantiene constante en términos reales (no se proyecta su propio
# crecimiento): proyectar población YA es una extrapolación considerable (ver heat/
# 2_heatwave_risk.py); inventar además una tasa de crecimiento del PIB añadiría un segundo
# supuesto especulativo encima del primero. Este es un proxy relativo de exposición
# económica, no una predicción de daños reales.
#
# Los pesos 40/30/15/15 (calor/inundación/sequía/incendio, ahora usados tanto por
# combined_risk como por financial_impact_eur) NO son arbitrarios: los daños económicos
# reales no son igual de costosos por unidad de riesgo entre hazards. Basado en JRC PESETA
# IV (el estudio de referencia de la Comisión Europea sobre costes económicos del cambio
# climático por hazard) y en pérdidas históricas agregadas (EM-DAT, Banco de España/
# Universidad de Mannheim 2025): el calor domina las estimaciones de daño en términos de
# bienestar (mortalidad/productividad laboral) en el sur de Europa; la inundación es el
# segundo mayor coste pero muy concentrado en eventos puntuales (p.ej. la DANA de Valencia
# 2024, >20% del PIB provincial en un solo evento); sequía e incendio quedan en un orden de
# magnitud menor en año medio, aunque con picos regionales severos. Esto es una
# aproximación de orden de magnitud, no una calibración precisa: las fuentes mezclan
# horizontes temporales, escenarios de calentamiento y metodologías (pérdida de bienestar
# vs. daño directo a activos) que no son directamente comparables entre sí - ver README.
BOUNDARIES_DIR = "shared/boundaries"
INPUT_DIR = "combined/output"
OUTPUT_DIR = "combined/output"

INE_TABLA_PADRON = "29005"
INE_TABLA_PROYECCION_PROVINCIAL = "36725"
INE_TABLA_PIB_PROVINCIAL = "76926"

AÑOS = [2030, 2050]
ESCENARIOS = ['rcp4_5', 'rcp8_5']

# 1. Cargar el mapa de municipios y su población actual (mismo patrón que heat/wildfire).
municipios_base = gpd.read_file(f"{BOUNDARIES_DIR}/municipios_espana.shp")
municipios_base = municipios_base.to_crs(epsg=4326)
municipios_base['ine_code'] = municipios_base['NATCODE'].str[-5:]
municipios_base['codigo_provincia'] = municipios_base['ine_code'].str[:2]

resp = requests.get(
    f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{INE_TABLA_PADRON}",
    params={"nult": 1, "det": 3, "tip": "AM"},
    timeout=120,
)
resp.raise_for_status()
poblacion_por_municipio = {}
for serie in resp.json():
    metadata = {m['Variable']['Nombre']: m for m in serie['MetaData']}
    if metadata.get('Sexo', {}).get('Nombre') != 'Total':
        continue
    ine_code = metadata['Municipios']['Codigo']
    if serie['Data']:
        poblacion_por_municipio[ine_code] = serie['Data'][0]['Valor']
municipios_base['poblacion'] = municipios_base['ine_code'].map(poblacion_por_municipio)

# 2. Factores de crecimiento de población por provincia a 2030/2050 (idéntico a heat/
# flood/drought/wildfire - ver heat/2_heatwave_risk.py para el razonamiento completo).
resp_prov = requests.get(
    f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{INE_TABLA_PROYECCION_PROVINCIAL}",
    params={"det": 3, "tip": "AM"},
    timeout=120,
)
resp_prov.raise_for_status()
poblacion_provincia = {}
for serie in resp_prov.json():
    metadata = {m['Variable']['Nombre']: m for m in serie['MetaData']}
    if metadata.get('Lugar de nacimiento', {}).get('Nombre') != 'Total':
        continue
    provincia_meta = metadata.get('Provincias')
    if provincia_meta is None or not provincia_meta['Codigo']:
        continue
    codigo_provincia = provincia_meta['Codigo']
    for punto in serie['Data']:
        poblacion_provincia.setdefault(codigo_provincia, {})[punto['Anyo']] = punto['Valor']

factor_2030_por_provincia = {}
factor_2050_por_provincia = {}
for codigo_provincia, serie_anual in poblacion_provincia.items():
    base_2026 = serie_anual.get(2026)
    valor_2030 = serie_anual.get(2030)
    valor_2041 = serie_anual.get(2041)
    if base_2026 and valor_2030:
        factor_2030_por_provincia[codigo_provincia] = valor_2030 / base_2026
    if base_2026 and valor_2041:
        tasa_anual = (valor_2041 / base_2026) ** (1 / 15)
        factor_2050_por_provincia[codigo_provincia] = (valor_2041 / base_2026) * (tasa_anual ** 9)

municipios_base['poblacion_2030'] = municipios_base['poblacion'] * municipios_base['codigo_provincia'].map(factor_2030_por_provincia)
municipios_base['poblacion_2050'] = municipios_base['poblacion'] * municipios_base['codigo_provincia'].map(factor_2050_por_provincia)

# 3. PIB provincial (Contabilidad Regional de España, tabla 76926): "PRODUCTO INTERIOR
# BRUTO A PRECIOS DE MERCADO" en miles de euros, último año disponible. Se divide entre la
# población ACTUAL de la provincia (suma de la población municipal actual, no la
# proyectada) para obtener el PIB per cápita de referencia.
resp_pib = requests.get(
    f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{INE_TABLA_PIB_PROVINCIAL}",
    params={"det": 3, "tip": "AM"},
    timeout=120,
)
resp_pib.raise_for_status()
pib_por_provincia = {}
for serie in resp_pib.json():
    metadata = {m['Variable']['Nombre']: m for m in serie['MetaData']}
    rama = metadata.get('ramas de actividad', {})
    if rama.get('Nombre') != 'PRODUCTO INTERIOR BRUTO A PRECIOS DE MERCADO':
        continue
    provincia_meta = metadata.get('Provincias')
    if provincia_meta is None:
        continue
    codigo_provincia = provincia_meta['Codigo']
    if serie['Data']:
        # Miles de euros -> euros. El primer dato es el año más reciente disponible.
        pib_por_provincia[codigo_provincia] = serie['Data'][0]['Valor'] * 1000

poblacion_actual_provincia = municipios_base.groupby('codigo_provincia')['poblacion'].sum()
pib_per_capita_provincia = {
    codigo: pib / poblacion_actual_provincia.get(codigo, float('nan'))
    for codigo, pib in pib_por_provincia.items()
}
municipios_base['pib_per_capita'] = municipios_base['codigo_provincia'].map(pib_per_capita_provincia)

for escenario in ESCENARIOS:
    for año in AÑOS:
        combinado = gpd.read_file(f"{INPUT_DIR}/municipios_combined_risk_{año}_{escenario}.geojson")[
            ['ine_code', 'combined_risk']
        ]

        tabla = municipios_base.merge(combinado, on='ine_code', how='left')
        tabla['valor_economico_eur'] = tabla[f'poblacion_{año}'] * tabla['pib_per_capita']
        tabla['financial_impact_eur'] = tabla['valor_economico_eur'] * tabla['combined_risk']
        # = financial_impact_eur / población: la población se cancela algebraicamente
        # (población x PIB per cápita x riesgo / población = PIB per cápita x riesgo), así
        # que se calcula directamente en vez de dividir - evita además un NaN/división por
        # cero en los ~88 municipios sin población (mancomunidades, ver Known limitations).
        # Al no depender de la población, esta cifra solo cambia por provincia (PIB per
        # cápita) y por riesgo combinado, no por el tamaño del municipio: es la métrica
        # pensada para comparar municipios de tamaños muy distintos entre sí, a diferencia
        # de financial_impact_eur (total), que crece con la población y por eso las
        # grandes ciudades dominan siempre su ranking.
        tabla['financial_impact_eur_per_capita'] = tabla['pib_per_capita'] * tabla['combined_risk']

        salida = f"{OUTPUT_DIR}/municipios_financial_impact_{año}_{escenario}.geojson"
        tabla.to_file(salida, driver="GeoJSON")

        columnas_lite = [
            'NAMEUNIT', 'ine_code', 'financial_impact_eur', 'financial_impact_eur_per_capita',
            'valor_economico_eur', 'pib_per_capita', 'combined_risk', 'geometry',
        ]
        tabla_lite = tabla[columnas_lite].copy()
        tabla_lite['geometry'] = tabla_lite.geometry.simplify(0.001, preserve_topology=True)
        salida_lite = f"{OUTPUT_DIR}/municipios_financial_impact_{año}_{escenario}_lite.geojson"
        tabla_lite.to_file(salida_lite, driver="GeoJSON")

        print(f"Impacto financiero finalizado: {salida} / {salida_lite}")

"""Tests para App.py: smoke tests (la app renderiza sin excepciones en cada combinación
de escenario/variable) y comprobaciones de cordura sobre los datos que muestra.

Ejecutar con: pytest test_app.py -v
"""
import functools
import os

import geopandas as gpd
import pytest
from streamlit.testing.v1 import AppTest

ESCENARIOS = ["RCP4.5", "RCP8.5"]
VARIABLES = [
    "Riesgo de mortalidad por calor",
    "Índice de calor (día, temp. máxima)",
    "Índice de calor (noche, temp. mínima)",
]
AÑOS = [2030, 2050]
ESCENARIOS_ARCHIVO = ['rcp4_5', 'rcp8_5']

# Municipios sin heat_mortality_risk documentados en el README: ~88 mancomunidades sin
# población (Comunidades de Villa y Tierra) + ~33 municipios costeros/exclaves sin dato de
# temperatura (grid de EURO-CORDEX enmascara el mar). Un número muy por encima de esto
# indicaría una regresión real, no el hueco de datos ya conocido.
MAX_NULOS_ESPERADOS = 130


@functools.lru_cache(maxsize=None)
def _cargar_app(escenario=None, variable=None):
    # Cada AppTest.from_file tarda ~15-20s (recorta y renderiza los 4 geojsons), así que se
    # cachea por combinación de escenario/variable: varios tests sobre la misma combinación
    # reutilizan la misma ejecución en lugar de relanzar la app cada vez.
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    if variable is not None:
        at.selectbox[1].set_value(variable).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


# --- Smoke tests: la app debe cargar sin excepciones en cualquier combinación ---

def test_estado_por_defecto():
    at = _cargar_app()
    assert len(at.selectbox) == 2
    assert at.selectbox[0].value == "RCP4.5"
    assert at.selectbox[1].value == "Riesgo de mortalidad por calor"


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES)
def test_app_renderiza_sin_excepciones(escenario, variable):
    _cargar_app(escenario, variable)


# --- Comprobaciones sobre las tablas que muestra la app ---

@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES)
def test_tablas_tienen_las_columnas_esperadas(escenario, variable):
    at = _cargar_app(escenario, variable)
    assert len(at.dataframe) == 2, "Deberían mostrarse las 2 tablas (incrementos y ciudades)"
    for tabla in at.dataframe:
        columnas = list(tabla.value.columns)
        assert columnas[0] == "Municipio"
        assert columnas[-1] == "Incremento"
        assert len(columnas) == 4


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES)
def test_tabla_top_incrementos_tiene_10_filas(escenario, variable):
    at = _cargar_app(escenario, variable)
    tabla_incrementos = at.dataframe[0].value
    assert len(tabla_incrementos) == 10
    # Debe estar ordenada de mayor a menor incremento
    assert tabla_incrementos['Incremento'].is_monotonic_decreasing


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES)
def test_tabla_top_ciudades_tiene_10_filas_y_madrid_primero(escenario, variable):
    at = _cargar_app(escenario, variable)
    tabla_ciudades = at.dataframe[1].value
    assert len(tabla_ciudades) == 10
    assert tabla_ciudades['Municipio'].iloc[0] == 'Madrid'  # ciudad más poblada de España


# --- Comprobaciones directamente sobre los geojson lite (no requieren Streamlit) ---

def _ruta_lite(año, escenario):
    return f"heat/output/municipios_heatwave_risk_{año}_{escenario}_lite.geojson"


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_geojson_lite_existe_y_tiene_las_columnas_esperadas(año, escenario):
    ruta = _ruta_lite(año, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta 2_heatwave_risk.py"
    gdf = gpd.read_file(ruta)
    for columna in ['NAMEUNIT', 'ine_code', 'heat_mortality_risk', 'heat_index_max_c', 'heat_index_min_c', 'geometry']:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_mortality_risk_nulos_dentro_de_lo_esperado(año, escenario):
    gdf = gpd.read_file(_ruta_lite(año, escenario))
    nulos = int(gdf['heat_mortality_risk'].isna().sum())
    assert nulos <= MAX_NULOS_ESPERADOS, (
        f"{año}/{escenario}: {nulos} municipios sin heat_mortality_risk, "
        f"se esperaban como mucho {MAX_NULOS_ESPERADOS} (ver README, Known limitations)"
    )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_mortality_risk_en_rango_0_1(año, escenario):
    gdf = gpd.read_file(_ruta_lite(año, escenario))
    valores = gdf['heat_mortality_risk'].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 1.0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_index_en_rango_fisico_razonable(año, escenario):
    gdf = gpd.read_file(_ruta_lite(año, escenario))
    for columna in ['heat_index_max_c', 'heat_index_min_c']:
        valores = gdf[columna].dropna()
        assert valores.min() > -10, f"{columna} en {año}/{escenario}: mínimo {valores.min()} sospechosamente bajo"
        assert valores.max() < 70, f"{columna} en {año}/{escenario}: máximo {valores.max()} sospechosamente alto"


def test_heat_index_max_siempre_mayor_o_igual_que_min():
    # El índice de calor diurno (temp. máxima) nunca debería ser menor que el nocturno
    # (temp. mínima) para el mismo municipio: si lo fuera, indicaría un cruce de columnas.
    for año in AÑOS:
        for escenario in ESCENARIOS_ARCHIVO:
            gdf = gpd.read_file(_ruta_lite(año, escenario))
            comparables = gdf.dropna(subset=['heat_index_max_c', 'heat_index_min_c'])
            assert (comparables['heat_index_max_c'] >= comparables['heat_index_min_c']).all()


def test_calentamiento_2030_a_2050_es_mayoritariamente_positivo():
    # No todos los municipios individuales tienen por qué calentarse (ruido de un único
    # modelo de humedad), pero la gran mayoría sí debería, dado el escenario de cambio
    # climático. Un fallo aquí probablemente indica una regresión de normalización como la
    # que motivó este fichero de tests (ver README).
    for escenario in ESCENARIOS_ARCHIVO:
        g30 = gpd.read_file(_ruta_lite(2030, escenario)).set_index('ine_code')
        g50 = gpd.read_file(_ruta_lite(2050, escenario)).set_index('ine_code')
        comunes = g30.index.intersection(g50.index)
        delta = g50.loc[comunes, 'heat_mortality_risk'] - g30.loc[comunes, 'heat_mortality_risk']
        delta = delta.dropna()
        fraccion_positiva = (delta > 0).mean()
        assert fraccion_positiva > 0.9, (
            f"{escenario}: solo el {fraccion_positiva:.0%} de los municipios muestra un "
            f"incremento de riesgo 2030->2050 (se esperaba >90%)"
        )

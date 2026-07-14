"""Tests para la app multi-página (App.py + pages/*.py): smoke tests (cada página
renderiza sin excepciones) y comprobaciones de cordura sobre los datos que muestran.

Ejecutar con: pytest test_app.py -v
"""
import functools
import os

import geopandas as gpd
import pytest
from streamlit.testing.v1 import AppTest

PAGINAS = ["pages/heat.py", "pages/flood.py", "pages/drought.py", "pages/wildfire.py", "pages/combined.py"]

ESCENARIOS = ["RCP4.5", "RCP8.5"]
VARIABLES_CALOR = [
    "Riesgo de mortalidad por calor",
    "Índice de calor (día, temp. máxima)",
    "Índice de calor (noche, temp. mínima)",
]
VARIABLES_SEQUIA = [
    "Duración de la sequía (meses/año)",
    "Magnitud de la sequía (índice SPI-3)",
]
AÑOS = [2030, 2050]
ESCENARIOS_ARCHIVO = ['rcp4_5', 'rcp8_5']

# Municipios sin heat_mortality_risk documentados en el README: ~88 mancomunidades sin
# población (Comunidades de Villa y Tierra) + ~33 municipios costeros/exclaves sin dato de
# temperatura (grid de EURO-CORDEX enmascara el mar). Un número muy por encima de esto
# indicaría una regresión real, no el hueco de datos ya conocido.
MAX_NULOS_ESPERADOS = 130


@functools.lru_cache(maxsize=None)
def _cargar_app():
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


@functools.lru_cache(maxsize=None)
def _cargar_heat(escenario=None, variable=None):
    # Cada ejecución tarda ~15-20s la primera vez (recorta y renderiza 4 geojsons), así
    # que se cachea por combinación de escenario/variable: varios tests sobre la misma
    # combinación reutilizan la misma ejecución en lugar de relanzarla cada vez.
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    at.switch_page("pages/heat.py").run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    if variable is not None:
        at.selectbox[1].set_value(variable).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


@functools.lru_cache(maxsize=None)
def _cargar_drought(escenario=None, variable=None):
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    at.switch_page("pages/drought.py").run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    if variable is not None:
        at.selectbox[1].set_value(variable).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


# --- Smoke tests: cada página debe cargar sin excepciones ---

@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_renderiza_sin_excepciones(pagina):
    at = _cargar_app()
    at.switch_page(pagina).run()
    assert not at.exception, f"{pagina} lanzó una excepción: {at.exception}"


def test_wildfire_muestra_aviso_no_implementado():
    at = _cargar_app()
    at.switch_page("pages/wildfire.py").run()
    assert len(at.info) >= 1, "pages/wildfire.py debería mostrar un st.info de 'no implementado'"


# --- Página de calor: mismas comprobaciones que antes, sobre pages/heat.py ---

def test_heat_estado_por_defecto():
    at = _cargar_heat()
    assert len(at.selectbox) == 2
    assert at.selectbox[0].value == "RCP4.5"
    assert at.selectbox[1].value == "Riesgo de mortalidad por calor"


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_CALOR)
def test_heat_renderiza_sin_excepciones(escenario, variable):
    _cargar_heat(escenario, variable)


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_CALOR)
def test_heat_tablas_tienen_las_columnas_esperadas(escenario, variable):
    at = _cargar_heat(escenario, variable)
    assert len(at.dataframe) == 2, "Deberían mostrarse las 2 tablas (incrementos y ciudades)"
    for tabla in at.dataframe:
        columnas = list(tabla.value.columns)
        assert columnas[0] == "Municipio"
        assert columnas[-1] == "Incremento"
        assert len(columnas) == 4


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_CALOR)
def test_heat_tabla_top_incrementos_tiene_10_filas(escenario, variable):
    at = _cargar_heat(escenario, variable)
    tabla_incrementos = at.dataframe[0].value
    assert len(tabla_incrementos) == 10
    assert tabla_incrementos['Incremento'].is_monotonic_decreasing


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_CALOR)
def test_heat_tabla_top_ciudades_tiene_10_filas_y_madrid_primero(escenario, variable):
    at = _cargar_heat(escenario, variable)
    tabla_ciudades = at.dataframe[1].value
    assert len(tabla_ciudades) == 10
    assert tabla_ciudades['Municipio'].iloc[0] == 'Madrid'  # ciudad más poblada de España


# --- Página de sequía: misma estructura que la de calor (mapas 2030/2050 + 2 tablas) ---

def test_drought_estado_por_defecto():
    at = _cargar_drought()
    assert len(at.selectbox) == 2
    assert at.selectbox[0].value == "RCP4.5"
    assert at.selectbox[1].value == "Duración de la sequía (meses/año)"


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_SEQUIA)
def test_drought_renderiza_sin_excepciones(escenario, variable):
    _cargar_drought(escenario, variable)


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_SEQUIA)
def test_drought_tablas_tienen_las_columnas_esperadas(escenario, variable):
    at = _cargar_drought(escenario, variable)
    assert len(at.dataframe) == 2, "Deberían mostrarse las 2 tablas (incrementos y ciudades)"
    for tabla in at.dataframe:
        columnas = list(tabla.value.columns)
        assert columnas[0] == "Municipio"
        assert columnas[-1] == "Incremento"
        assert len(columnas) == 4


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_SEQUIA)
def test_drought_tabla_top_incrementos_tiene_10_filas(escenario, variable):
    at = _cargar_drought(escenario, variable)
    tabla_incrementos = at.dataframe[0].value
    assert len(tabla_incrementos) == 10
    assert tabla_incrementos['Incremento'].is_monotonic_decreasing


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_SEQUIA)
def test_drought_tabla_top_ciudades_tiene_10_filas_y_madrid_primero(escenario, variable):
    at = _cargar_drought(escenario, variable)
    tabla_ciudades = at.dataframe[1].value
    assert len(tabla_ciudades) == 10
    assert tabla_ciudades['Municipio'].iloc[0] == 'Madrid'  # ciudad más poblada de España


# --- Página de inundación ---

def test_flood_renderiza_con_cada_periodo_de_retorno():
    at = _cargar_app()
    at.switch_page("pages/flood.py").run()
    columnas_esperadas = ['Municipio', 'Afectados 2030', 'Afectados 2050', 'Incremento']
    for periodo in ["10 años (frecuente)", "100 años (ocasional)", "500 años (excepcional)"]:
        at.selectbox[0].set_value(periodo).run()
        assert not at.exception, f"{periodo}: {at.exception}"
        assert len(at.dataframe) == 4, "2 tablas MITECO (incrementos/ciudades) + 2 de caudal fluvial"
        tabla_incrementos = at.dataframe[0].value
        tabla_ciudades = at.dataframe[1].value
        assert len(tabla_incrementos) == 10
        assert len(tabla_ciudades) == 10
        assert list(tabla_incrementos.columns) == columnas_esperadas
        assert list(tabla_ciudades.columns) == columnas_esperadas
        assert tabla_incrementos['Incremento'].is_monotonic_decreasing
        assert tabla_ciudades['Municipio'].iloc[0] == 'Madrid'  # ciudad más poblada de España


def test_flood_caudal_renderiza_con_cada_escenario_y_periodo():
    at = _cargar_app()
    at.switch_page("pages/flood.py").run()
    for escenario in ["RCP4.5", "RCP8.5"]:
        at.selectbox[1].set_value(escenario).run()
        for periodo in ["2 años", "5 años", "10 años", "50 años"]:
            at.selectbox[2].set_value(periodo).run()
            assert not at.exception, f"{escenario}/{periodo}: {at.exception}"
            assert len(at.dataframe) == 4
            tabla_incrementos = at.dataframe[2].value
            tabla_ciudades = at.dataframe[3].value
            assert len(tabla_incrementos) == 10
            # Las 10 ciudades más grandes tienen cauce cercano en todos los combos probados,
            # pero no se exige aquí de forma estricta: un municipio sin cauce significativo
            # se omite (null), no se rellena con 0 (ver README, Known limitations).
            assert len(tabla_ciudades) == 10
            for tabla in (tabla_incrementos, tabla_ciudades):
                assert list(tabla.columns)[0] == 'Municipio'
                assert list(tabla.columns)[-1] == 'Incremento'
                assert len(tabla.columns) == 4
            assert tabla_incrementos['Incremento'].is_monotonic_decreasing


# --- Comprobaciones directamente sobre los geojson lite (no requieren Streamlit) ---

def _ruta_calor(año, escenario):
    return f"heat/output/municipios_heatwave_risk_{año}_{escenario}_lite.geojson"


def _ruta_sequia(año, escenario):
    return f"drought/output/municipios_drought_risk_{año}_{escenario}_lite.geojson"


RUTA_INUNDACION = "flood/output/municipios_inundacion_lite.geojson"

EPOCAS_CAUDAL = ['2011_2040', '2041_2070']


def _ruta_caudal(epoca, escenario):
    return f"flood/output/municipios_river_discharge_{epoca}_{escenario}_lite.geojson"


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_geojson_calor_existe_y_tiene_las_columnas_esperadas(año, escenario):
    ruta = _ruta_calor(año, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta heat/2_heatwave_risk.py"
    gdf = gpd.read_file(ruta)
    for columna in ['NAMEUNIT', 'ine_code', 'heat_mortality_risk', 'heat_index_max_c', 'heat_index_min_c', 'geometry']:
        assert columna in gdf.columns


def test_geojson_inundacion_existe_y_tiene_las_columnas_esperadas():
    assert os.path.exists(RUTA_INUNDACION), f"Falta {RUTA_INUNDACION} - ejecuta flood/3_flood_risk.py"
    gdf = gpd.read_file(RUTA_INUNDACION)
    columnas_esperadas = ['NAMEUNIT', 'ine_code', 'geometry']
    for periodo in ['t10', 't100', 't500']:
        columnas_esperadas += [
            f'flood_risk_{periodo}',
            f'flood_risk_{periodo}_poblacion_afectada',
            f'flood_risk_{periodo}_poblacion_afectada_2030',
            f'flood_risk_{periodo}_poblacion_afectada_2050',
        ]
    for columna in columnas_esperadas:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_mortality_risk_nulos_dentro_de_lo_esperado(año, escenario):
    gdf = gpd.read_file(_ruta_calor(año, escenario))
    nulos = int(gdf['heat_mortality_risk'].isna().sum())
    assert nulos <= MAX_NULOS_ESPERADOS, (
        f"{año}/{escenario}: {nulos} municipios sin heat_mortality_risk, "
        f"se esperaban como mucho {MAX_NULOS_ESPERADOS} (ver README, Known limitations)"
    )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_mortality_risk_en_rango_0_1(año, escenario):
    gdf = gpd.read_file(_ruta_calor(año, escenario))
    valores = gdf['heat_mortality_risk'].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 1.0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_heat_index_en_rango_fisico_razonable(año, escenario):
    gdf = gpd.read_file(_ruta_calor(año, escenario))
    for columna in ['heat_index_max_c', 'heat_index_min_c']:
        valores = gdf[columna].dropna()
        assert valores.min() > -10, f"{columna} en {año}/{escenario}: mínimo {valores.min()} sospechosamente bajo"
        assert valores.max() < 70, f"{columna} en {año}/{escenario}: máximo {valores.max()} sospechosamente alto"


def test_heat_index_max_siempre_mayor_o_igual_que_min():
    # El índice de calor diurno (temp. máxima) nunca debería ser menor que el nocturno
    # (temp. mínima) para el mismo municipio: si lo fuera, indicaría un cruce de columnas.
    for año in AÑOS:
        for escenario in ESCENARIOS_ARCHIVO:
            gdf = gpd.read_file(_ruta_calor(año, escenario))
            comparables = gdf.dropna(subset=['heat_index_max_c', 'heat_index_min_c'])
            assert (comparables['heat_index_max_c'] >= comparables['heat_index_min_c']).all()


def test_calentamiento_2030_a_2050_es_mayoritariamente_positivo():
    # No todos los municipios individuales tienen por qué calentarse (ruido de un único
    # modelo de humedad), pero la gran mayoría sí debería, dado el escenario de cambio
    # climático. Un fallo aquí probablemente indica una regresión de normalización como la
    # que motivó este fichero de tests (ver README).
    for escenario in ESCENARIOS_ARCHIVO:
        g30 = gpd.read_file(_ruta_calor(2030, escenario)).set_index('ine_code')
        g50 = gpd.read_file(_ruta_calor(2050, escenario)).set_index('ine_code')
        comunes = g30.index.intersection(g50.index)
        delta = g50.loc[comunes, 'heat_mortality_risk'] - g30.loc[comunes, 'heat_mortality_risk']
        delta = delta.dropna()
        fraccion_positiva = (delta > 0).mean()
        assert fraccion_positiva > 0.9, (
            f"{escenario}: solo el {fraccion_positiva:.0%} de los municipios muestra un "
            f"incremento de riesgo 2030->2050 (se esperaba >90%)"
        )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_geojson_sequia_existe_y_tiene_las_columnas_esperadas(año, escenario):
    ruta = _ruta_sequia(año, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta drought/2_drought_risk.py"
    gdf = gpd.read_file(ruta)
    for columna in ['NAMEUNIT', 'ine_code', 'drought_duration_months', 'drought_magnitude', 'geometry']:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_drought_sin_nulos(año, escenario):
    # A diferencia del calor (rejilla EURO-CORDEX ~11km que enmascara algo de costa), la
    # rejilla de sequía (~25km, sis-ecde-climate-indicators) cubre toda España sin huecos.
    gdf = gpd.read_file(_ruta_sequia(año, escenario))
    for columna in ['drought_duration_months', 'drought_magnitude']:
        assert int(gdf[columna].isna().sum()) == 0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_drought_duration_en_rango_fisico_razonable(año, escenario):
    # drought_duration_months es meses/año en sequía: como mucho 12.
    gdf = gpd.read_file(_ruta_sequia(año, escenario))
    valores = gdf['drought_duration_months']
    assert valores.min() >= 0.0
    assert valores.max() <= 12.0


def test_sequia_2030_a_2050_es_mayoritariamente_creciente():
    # No todos los municipios individuales tienen por qué empeorar (valores anuales
    # ruidosos incluso tras promediar una ventana de 20 años), pero la gran mayoría sí
    # debería bajo un escenario de cambio climático (verificado: ~74-88% en la práctica).
    for escenario in ESCENARIOS_ARCHIVO:
        g30 = gpd.read_file(_ruta_sequia(2030, escenario)).set_index('ine_code')
        g50 = gpd.read_file(_ruta_sequia(2050, escenario)).set_index('ine_code')
        comunes = g30.index.intersection(g50.index)
        for columna in ['drought_duration_months', 'drought_magnitude']:
            delta = g50.loc[comunes, columna] - g30.loc[comunes, columna]
            fraccion_positiva = (delta > 0).mean()
            assert fraccion_positiva > 0.7, (
                f"{escenario}/{columna}: solo el {fraccion_positiva:.0%} de los municipios "
                f"muestra un incremento 2030->2050 (se esperaba >70%)"
            )


@pytest.mark.parametrize("columna", ['flood_risk_t10', 'flood_risk_t100', 'flood_risk_t500'])
def test_flood_risk_en_rango_0_1(columna):
    gdf = gpd.read_file(RUTA_INUNDACION)
    valores = gdf[columna].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 1.0


def test_flood_risk_aumenta_con_el_periodo_de_retorno():
    # A igual municipio, el riesgo de inundación a T=500 casi siempre debería ser mayor
    # o igual que a T=100, y ese mayor o igual que a T=10 (cuanto más raro el evento, más
    # área/población afectada potencialmente). No se exige el 100%: cada periodo viene de
    # un estudio SNCZI procesado por separado, así que hay una pequeña fracción de
    # municipios (~0.2-0.4% en la práctica) donde no se cumple estrictamente.
    gdf = gpd.read_file(RUTA_INUNDACION)
    assert (gdf['flood_risk_t100'] >= gdf['flood_risk_t10']).mean() > 0.95
    assert (gdf['flood_risk_t500'] >= gdf['flood_risk_t100']).mean() > 0.95


@pytest.mark.parametrize("periodo", ['t10', 't100', 't500'])
def test_poblacion_afectada_2050_mayoritariamente_creciente(periodo):
    # La zona de inundación es fija; solo la población proyectada varía. La mayoría de
    # provincias españolas crecen de aquí a 2050 (verificado: ~81-84% de los municipios
    # afectados en la práctica), pero no todas (p.ej. Zamora, Jaén encogen), así que no
    # se exige el 100%.
    gdf = gpd.read_file(RUTA_INUNDACION)
    columna_2030 = f'flood_risk_{periodo}_poblacion_afectada_2030'
    columna_2050 = f'flood_risk_{periodo}_poblacion_afectada_2050'
    afectados = gdf[gdf[columna_2030] > 0]
    fraccion_creciente = (afectados[columna_2050] >= afectados[columna_2030]).mean()
    assert fraccion_creciente > 0.75, (
        f"{periodo}: solo el {fraccion_creciente:.0%} de los municipios afectados muestra "
        f"población proyectada creciente 2030->2050 (se esperaba >75%)"
    )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("epoca", EPOCAS_CAUDAL)
def test_geojson_caudal_existe_y_tiene_las_columnas_esperadas(epoca, escenario):
    ruta = _ruta_caudal(epoca, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta flood/5_river_discharge_risk.py"
    gdf = gpd.read_file(ruta)
    for columna in ['NAMEUNIT', 'ine_code', 'river_discharge_2y', 'river_discharge_5y', 'river_discharge_10y', 'river_discharge_50y', 'geometry']:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("epoca", EPOCAS_CAUDAL)
def test_caudal_nulos_dentro_de_lo_esperado(epoca, escenario):
    # Municipios sin cauce significativo dentro (ni cerca de su centroide): ~84 en la
    # práctica, de ~8100. Un número muy por encima indicaría una regresión real.
    gdf = gpd.read_file(_ruta_caudal(epoca, escenario))
    for columna in ['river_discharge_2y', 'river_discharge_5y', 'river_discharge_10y', 'river_discharge_50y']:
        nulos = int(gdf[columna].isna().sum())
        assert nulos <= 150, f"{epoca}/{escenario}/{columna}: {nulos} municipios sin dato (se esperaban <=150)"


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("epoca", EPOCAS_CAUDAL)
def test_caudal_no_negativo(epoca, escenario):
    gdf = gpd.read_file(_ruta_caudal(epoca, escenario))
    for columna in ['river_discharge_2y', 'river_discharge_5y', 'river_discharge_10y', 'river_discharge_50y']:
        valores = gdf[columna].dropna()
        assert valores.min() >= 0.0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("epoca", EPOCAS_CAUDAL)
def test_caudal_aumenta_con_el_periodo_de_retorno(epoca, escenario):
    # Igual que con flood_risk_tXX: a igual municipio, un periodo de retorno más raro
    # (50 años) debería implicar un caudal máximo mayor o igual que uno más frecuente
    # (2 años) - no se exige el 100%, solo la gran mayoría.
    gdf = gpd.read_file(_ruta_caudal(epoca, escenario))
    assert (gdf['river_discharge_5y'] >= gdf['river_discharge_2y']).mean() > 0.95
    assert (gdf['river_discharge_10y'] >= gdf['river_discharge_5y']).mean() > 0.95
    assert (gdf['river_discharge_50y'] >= gdf['river_discharge_10y']).mean() > 0.95

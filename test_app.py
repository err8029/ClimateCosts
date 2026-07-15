"""Tests para la app multi-página (App.py + pages/*.py): smoke tests (cada página
renderiza sin excepciones) y comprobaciones de cordura sobre los datos que muestran.

Ejecutar con: pytest test_app.py -v
"""
import functools
import os

import geopandas as gpd
import pytest
from streamlit.testing.v1 import AppTest

import auth

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
VARIABLES_INCENDIO = [
    "Riesgo de incendio forestal",
    "Índice de peligro de incendio (Canadian FWI)",
    "Días/año de peligro alto",
]
AÑOS = [2030, 2050]
ESCENARIOS_ARCHIVO = ['rcp4_5', 'rcp8_5']

# Municipios sin heat_mortality_risk documentados en el README: ~88 mancomunidades sin
# población (Comunidades de Villa y Tierra) + ~33 municipios costeros/exclaves sin dato de
# temperatura (grid de EURO-CORDEX enmascara el mar). Un número muy por encima de esto
# indicaría una regresión real, no el hueco de datos ya conocido.
MAX_NULOS_ESPERADOS = 130

def _sin_login(at):
    # Los tests de contenido no deben depender de (ni incluir en el repo) la contraseña
    # real de .streamlit/secrets.toml: en vez de rellenar el formulario, se preseedea
    # session_state con el mismo flag que pondría un login correcto (ver auth.py). Los
    # tests que sí ejercitan el mecanismo de login en sí están más abajo, en "--- Login ---".
    at.session_state['autenticado'] = True
    return at


@functools.lru_cache(maxsize=None)
def _cargar_app():
    at = AppTest.from_file("App.py", default_timeout=180)
    _sin_login(at)
    at.run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


@functools.lru_cache(maxsize=None)
def _cargar_heat(escenario=None, variable=None):
    # Cada ejecución tarda ~15-20s la primera vez (recorta y renderiza 4 geojsons), así
    # que se cachea por combinación de escenario/variable: varios tests sobre la misma
    # combinación reutilizan la misma ejecución en lugar de relanzarla cada vez.
    at = AppTest.from_file("App.py", default_timeout=180)
    _sin_login(at)
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
    _sin_login(at)
    at.run()
    at.switch_page("pages/drought.py").run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    if variable is not None:
        at.selectbox[1].set_value(variable).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


@functools.lru_cache(maxsize=None)
def _cargar_wildfire(escenario=None, variable=None):
    at = AppTest.from_file("App.py", default_timeout=180)
    _sin_login(at)
    at.run()
    at.switch_page("pages/wildfire.py").run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    if variable is not None:
        at.selectbox[1].set_value(variable).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


@functools.lru_cache(maxsize=None)
def _cargar_combinado(escenario=None):
    at = AppTest.from_file("App.py", default_timeout=180)
    _sin_login(at)
    at.run()
    at.switch_page("pages/combined.py").run()
    if escenario is not None:
        at.selectbox[0].set_value(escenario).run()
    assert not at.exception, f"La app lanzó una excepción: {at.exception}"
    return at


# --- Smoke tests: cada página debe cargar sin excepciones ---

@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_renderiza_sin_excepciones(pagina):
    at = _cargar_app()
    at.switch_page(pagina).run()
    assert not at.exception, f"{pagina} lanzó una excepción: {at.exception}"


# --- Login (auth.py) ---

def test_sin_login_la_app_no_muestra_navegacion():
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    assert not at.exception
    assert len(at.text_input) == 2, "Debería mostrarse el formulario de login (usuario + contraseña)"
    assert len(at.selectbox) == 0, "No debería poder verse ninguna página sin autenticarse"


def test_login_con_credenciales_incorrectas_falla():
    at = AppTest.from_file("App.py", default_timeout=180)
    at.run()
    at.text_input[0].set_value("usuario_incorrecto")
    at.text_input[1].set_value("contraseña_incorrecta")
    at.button[0].click().run()
    assert not at.exception
    assert len(at.error) >= 1
    assert len(at.selectbox) == 0, "No debería concederse acceso con credenciales incorrectas"


def test_session_state_autenticado_omite_el_formulario_de_login():
    # Instancia propia (no _cargar_app(), compartida/cacheada y mutada por otros tests vía
    # switch_page - dependía del orden de ejecución de los tests, ver commit).
    at = AppTest.from_file("App.py", default_timeout=180)
    _sin_login(at)
    at.run()
    assert not at.exception
    assert len(at.text_input) == 0, "No debería mostrarse el formulario de login"
    assert len(at.selectbox) > 0, "Tras autenticarse debería verse la página de calor (por defecto)"


def test_hash_contraseña_es_determinista_y_sensible_a_mayusculas():
    # Usa una contraseña sintética inventada aquí mismo, no la real de producción.
    salt = "00" * 16
    h1 = auth._hash_contraseña("clave-de-prueba", salt)
    h2 = auth._hash_contraseña("clave-de-prueba", salt)
    h3 = auth._hash_contraseña("Clave-De-Prueba", salt)
    assert h1 == h2
    assert h1 != h3


def test_credenciales_correctas_con_secretos_sinteticos(monkeypatch):
    # Verifica el mecanismo de verificación de principio a fin con un usuario/contraseña
    # sintéticos generados aquí mismo - nunca con la contraseña real, que vive solo en
    # .streamlit/secrets.toml (no versionado, ver .gitignore).
    usuario_prueba = "usuario_de_prueba"
    contraseña_prueba = "clave-sintetica-solo-para-este-test"
    salt = os.urandom(16).hex()
    hash_correcto = auth._hash_contraseña(contraseña_prueba, salt)

    monkeypatch.setattr(auth.st, "secrets", {
        "auth": {"username": usuario_prueba, "password_hash": hash_correcto, "password_salt": salt},
    })

    assert auth._credenciales_correctas(usuario_prueba, contraseña_prueba)
    assert not auth._credenciales_correctas(usuario_prueba, "clave-incorrecta")
    assert not auth._credenciales_correctas("otro_usuario", contraseña_prueba)


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


# --- Página de incendios: misma estructura que la de calor/sequía ---

def test_wildfire_estado_por_defecto():
    at = _cargar_wildfire()
    assert len(at.selectbox) == 2
    assert at.selectbox[0].value == "RCP4.5"
    assert at.selectbox[1].value == "Riesgo de incendio forestal"


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_INCENDIO)
def test_wildfire_renderiza_sin_excepciones(escenario, variable):
    _cargar_wildfire(escenario, variable)


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_INCENDIO)
def test_wildfire_tablas_tienen_las_columnas_esperadas(escenario, variable):
    at = _cargar_wildfire(escenario, variable)
    assert len(at.dataframe) == 2, "Deberían mostrarse las 2 tablas (incrementos y ciudades)"
    for tabla in at.dataframe:
        columnas = list(tabla.value.columns)
        assert columnas[0] == "Municipio"
        assert columnas[-1] == "Incremento"
        assert len(columnas) == 4


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_INCENDIO)
def test_wildfire_tabla_top_incrementos_tiene_10_filas(escenario, variable):
    at = _cargar_wildfire(escenario, variable)
    tabla_incrementos = at.dataframe[0].value
    assert len(tabla_incrementos) == 10
    assert tabla_incrementos['Incremento'].is_monotonic_decreasing


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("variable", VARIABLES_INCENDIO)
def test_wildfire_tabla_top_ciudades_y_madrid_primero(escenario, variable):
    at = _cargar_wildfire(escenario, variable)
    tabla_ciudades = at.dataframe[1].value
    # A diferencia de heat/drought: València y Alacant/Alicante caen en la franja costera
    # sin dato de este indicador (ver README, Known limitations), así que solo 8 de las 10
    # ciudades de TOP10_CIUDADES aparecen aquí.
    assert len(tabla_ciudades) == 8
    assert tabla_ciudades['Municipio'].iloc[0] == 'Madrid'  # ciudad más poblada de España


# --- Página combinada: sección de riesgo combinado (25% cada hazard) ---

def test_combinado_estado_por_defecto():
    at = _cargar_combinado()
    assert len(at.selectbox) == 1
    assert at.selectbox[0].value == "RCP4.5"


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_combinado_renderiza_sin_excepciones(escenario):
    _cargar_combinado(escenario)


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_combinado_tablas_tienen_las_columnas_esperadas(escenario):
    at = _cargar_combinado(escenario)
    assert len(at.dataframe) == 2, "Deberían mostrarse las 2 tablas (incrementos y ciudades)"
    for tabla in at.dataframe:
        columnas = list(tabla.value.columns)
        assert columnas[0] == "Municipio"
        assert columnas[-1] == "Incremento"
        assert len(columnas) == 4


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_combinado_tabla_top_incrementos_tiene_10_filas(escenario):
    at = _cargar_combinado(escenario)
    tabla_incrementos = at.dataframe[0].value
    assert len(tabla_incrementos) == 10
    assert tabla_incrementos['Incremento'].is_monotonic_decreasing


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_combinado_tabla_top_ciudades_y_madrid_primero(escenario):
    at = _cargar_combinado(escenario)
    tabla_ciudades = at.dataframe[1].value
    # Hereda el hueco costero de wildfire_risk (ver su página): solo 8 de las 10 ciudades.
    assert len(tabla_ciudades) == 8
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


def _ruta_incendio(año, escenario):
    return f"wildfire/output/municipios_wildfire_risk_{año}_{escenario}_lite.geojson"


# Municipios sin wildfire_risk: ~88 mancomunidades sin población (igual que heat) + ~535
# municipios costeros sin dato de peligro de incendio (la rejilla de sis-ecde-climate-
# indicators para este indicador enmascara una franja costera bastante más ancha que la de
# temperatura de heat - ver README, Known limitations).
MAX_NULOS_ESPERADOS_INCENDIO = 700


def _ruta_combinado(año, escenario):
    return f"combined/output/municipios_combined_risk_{año}_{escenario}_lite.geojson"


# combined_risk exige los 4 componentes (calor/inundación/sequía/incendio) presentes a la
# vez: en la práctica esto queda dominado por el hueco de incendio (~618, muy cercano a su
# propio MAX_NULOS_ESPERADOS_INCENDIO), así que se reutiliza el mismo límite.
MAX_NULOS_ESPERADOS_COMBINADO = MAX_NULOS_ESPERADOS_INCENDIO


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


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_geojson_incendio_existe_y_tiene_las_columnas_esperadas(año, escenario):
    ruta = _ruta_incendio(año, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta wildfire/2_wildfire_risk.py"
    gdf = gpd.read_file(ruta)
    for columna in ['NAMEUNIT', 'ine_code', 'wildfire_risk', 'fire_weather_index', 'high_fire_danger_days', 'geometry']:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_wildfire_risk_nulos_dentro_de_lo_esperado(año, escenario):
    gdf = gpd.read_file(_ruta_incendio(año, escenario))
    nulos = int(gdf['wildfire_risk'].isna().sum())
    assert nulos <= MAX_NULOS_ESPERADOS_INCENDIO, (
        f"{año}/{escenario}: {nulos} municipios sin wildfire_risk, "
        f"se esperaban como mucho {MAX_NULOS_ESPERADOS_INCENDIO} (ver README, Known limitations)"
    )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_wildfire_risk_en_rango_0_1(año, escenario):
    gdf = gpd.read_file(_ruta_incendio(año, escenario))
    valores = gdf['wildfire_risk'].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 1.0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_high_fire_danger_days_no_supera_365(año, escenario):
    gdf = gpd.read_file(_ruta_incendio(año, escenario))
    valores = gdf['high_fire_danger_days'].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 365.0


def test_riesgo_incendio_2030_a_2050_es_mayoritariamente_creciente():
    # Igual que con heat_mortality_risk: no todos los municipios individuales tienen por
    # qué empeorar, pero la gran mayoría sí debería bajo cambio climático (verificado:
    # ~98-100% en la práctica).
    for escenario in ESCENARIOS_ARCHIVO:
        g30 = gpd.read_file(_ruta_incendio(2030, escenario)).set_index('ine_code')
        g50 = gpd.read_file(_ruta_incendio(2050, escenario)).set_index('ine_code')
        comunes = g30.index.intersection(g50.index)
        delta = g50.loc[comunes, 'wildfire_risk'] - g30.loc[comunes, 'wildfire_risk']
        delta = delta.dropna()
        fraccion_positiva = (delta > 0).mean()
        assert fraccion_positiva > 0.9, (
            f"{escenario}: solo el {fraccion_positiva:.0%} de los municipios muestra un "
            f"incremento de riesgo de incendio 2030->2050 (se esperaba >90%)"
        )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_geojson_combinado_existe_y_tiene_las_columnas_esperadas(año, escenario):
    ruta = _ruta_combinado(año, escenario)
    assert os.path.exists(ruta), f"Falta {ruta} - ejecuta combined/1_combined_risk.py"
    gdf = gpd.read_file(ruta)
    columnas_esperadas = ['NAMEUNIT', 'ine_code', 'combined_risk', 'calor_norm', 'inundacion_norm', 'sequia_norm', 'incendio_norm', 'geometry']
    for columna in columnas_esperadas:
        assert columna in gdf.columns


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_combined_risk_nulos_dentro_de_lo_esperado(año, escenario):
    gdf = gpd.read_file(_ruta_combinado(año, escenario))
    nulos = int(gdf['combined_risk'].isna().sum())
    assert nulos <= MAX_NULOS_ESPERADOS_COMBINADO, (
        f"{año}/{escenario}: {nulos} municipios sin combined_risk, "
        f"se esperaban como mucho {MAX_NULOS_ESPERADOS_COMBINADO} (ver README, Known limitations)"
    )


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_combined_risk_en_rango_0_1(año, escenario):
    gdf = gpd.read_file(_ruta_combinado(año, escenario))
    valores = gdf['combined_risk'].dropna()
    assert valores.min() >= 0.0
    assert valores.max() <= 1.0


@pytest.mark.parametrize("escenario", ESCENARIOS_ARCHIVO)
@pytest.mark.parametrize("año", AÑOS)
def test_combined_risk_es_la_media_de_sus_4_componentes(año, escenario):
    # Comprobación de cordura directa sobre la fórmula (25% cada uno): si algún componente
    # se pierde o se pesa distinto por error, este test lo detecta.
    gdf = gpd.read_file(_ruta_combinado(año, escenario)).dropna(
        subset=['combined_risk', 'calor_norm', 'inundacion_norm', 'sequia_norm', 'incendio_norm']
    )
    media_componentes = gdf[['calor_norm', 'inundacion_norm', 'sequia_norm', 'incendio_norm']].mean(axis=1)
    assert (gdf['combined_risk'] - media_componentes).abs().max() < 1e-9


def test_riesgo_combinado_2030_a_2050_es_mayoritariamente_creciente():
    # Umbral más bajo que en los hazards individuales (>90%): la sequía por sí sola solo
    # crece en ~73-88% de los municipios (ver su página), lo que arrastra un poco a la baja
    # la fracción creciente del combinado (verificado: ~85-93% en la práctica).
    for escenario in ESCENARIOS_ARCHIVO:
        g30 = gpd.read_file(_ruta_combinado(2030, escenario)).set_index('ine_code')
        g50 = gpd.read_file(_ruta_combinado(2050, escenario)).set_index('ine_code')
        comunes = g30.index.intersection(g50.index)
        delta = g50.loc[comunes, 'combined_risk'] - g30.loc[comunes, 'combined_risk']
        delta = delta.dropna()
        fraccion_positiva = (delta > 0).mean()
        assert fraccion_positiva > 0.8, (
            f"{escenario}: solo el {fraccion_positiva:.0%} de los municipios muestra un "
            f"incremento de riesgo combinado 2030->2050 (se esperaba >80%)"
        )


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

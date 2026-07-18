import glob

import pandas as pd

# Este script (y el resto del proyecto) se ejecuta desde la raíz del repositorio, p.ej.:
# python electricity/2_electricity_cost.py
#
# Modelo simplificado de "orden de mérito" (merit order): estima cuánta demanda eléctrica
# española queda sin cubrir por las fuentes de coste marginal ~0 (solar, eólica, hidráulica)
# y el nuclear (asumido fijo, ver más abajo) - esa "demanda residual" es la que hay que
# cubrir con centrales de ciclo combinado de gas (CCGT), la tecnología que casi siempre fija
# el precio marginal del mercado eléctrico español (ver README para fuentes). El coste
# adicional del sistema por cambio climático es, en esta aproximación, esa demanda residual
# multiplicada por un precio de referencia del CCGT.
#
# Esto es un proxy de orden de magnitud, no un modelo de despacho real (no hay optimización
# de unidades, no hay interconexión con Francia/Portugal, no hay almacenamiento/baterías) -
# ver Known limitations, README.
INPUT_DIR = "electricity/input"
OUTPUT_DIR = "electricity/output"

AÑOS = [2030, 2050]
ESCENARIOS = ['rcp_4_5', 'rcp_8_5']
VENTANA = {2030: (2021, 2040), 2050: (2041, 2060)}  # mismo patrón que drought/wildfire

# Potencia instalada de España a cierre de 2024 (REE, "Potencia instalada 2024" /
# sistemaelectrico-ree.es): 129 GW totales, eólica 24.9%, solar fotovoltaica 25.1% -> ~32.1
# y ~32.4 GW respectivamente. Se mantiene CONSTANTE (no se proyecta su crecimiento futuro):
# el propio indicador climático ya captura cómo cambia la eficiencia (factor de capacidad)
# de la flota actual con el clima; añadir además una proyección de nueva potencia instalada
# sería un segundo supuesto especulativo encima del primero (mismo criterio que el PIB per
# cápita constante en combined/2_financial_impact.py).
POTENCIA_EOLICA_MW = 32_100
POTENCIA_SOLAR_MW = 32_400
HORAS_AÑO = 8760

# Generación nuclear: capacidad ~7.1 GW (7 reactores), factor de capacidad muy estable
# (~85-90%, apenas depende del clima a esta escala de aproximación) -> ~55 TWh/año, cifra
# habitual citada para España (~20% del mix de generación). Se mantiene fija por la misma
# razón que la potencia eólica/solar.
GENERACION_NUCLEAR_MWH = 55_000_000

# Precio de referencia del CCGT (tecnología marginal en el mercado español la mayoría de
# horas, MIBEL): ~90 €/MWh, orden de magnitud de la media 2025 (~87-148 €/MWh según fuentes
# citadas en el README). Es una única banda de precio simplificada, no una curva de oferta
# completa por tecnología - ver Known limitations.
PRECIO_CCGT_EUR_MWH = 90


def leer_csv_energia(patron):
    ruta = glob.glob(f"{INPUT_DIR}/{patron}")[0]
    with open(ruta, encoding='utf-8') as fh:
        lineas = fh.readlines()
    fila_cabecera = next(i for i, l in enumerate(lineas) if l.startswith('Date,'))
    tabla = pd.read_csv(ruta, skiprows=fila_cabecera)
    tabla['Date'] = pd.to_datetime(tabla['Date'])
    tabla['año'] = tabla['Date'].dt.year
    return tabla.set_index('año')['ES']


resultados = []
for escenario in ESCENARIOS:
    demanda = leer_csv_energia(f"electricity_raw_energia_{escenario}/*EDM*.csv")
    hidro_embalse = leer_csv_energia(f"electricity_raw_energia_{escenario}/*HRE*.csv")
    hidro_fluyente = leer_csv_energia(f"electricity_raw_energia_{escenario}/*HRO*.csv")
    factor_solar = leer_csv_energia(f"electricity_raw_factor_capacidad_{escenario}/*SPV*.csv")
    factor_eolico = leer_csv_energia(f"electricity_raw_factor_capacidad_{escenario}/*WON*.csv")

    for año in AÑOS:
        y0, y1 = VENTANA[año]
        ventana_años = range(y0, y1 + 1)

        demanda_mwh = demanda.loc[demanda.index.isin(ventana_años)].mean()
        hidro_mwh = (
            hidro_embalse.loc[hidro_embalse.index.isin(ventana_años)].mean()
            + hidro_fluyente.loc[hidro_fluyente.index.isin(ventana_años)].mean()
        )
        solar_mwh = factor_solar.loc[factor_solar.index.isin(ventana_años)].mean() * POTENCIA_SOLAR_MW * HORAS_AÑO
        eolica_mwh = factor_eolico.loc[factor_eolico.index.isin(ventana_años)].mean() * POTENCIA_EOLICA_MW * HORAS_AÑO

        residual_mwh = max(0.0, demanda_mwh - hidro_mwh - solar_mwh - eolica_mwh - GENERACION_NUCLEAR_MWH)
        coste_sistema_eur = residual_mwh * PRECIO_CCGT_EUR_MWH

        resultados.append({
            'año': año,
            'escenario': escenario,
            'demanda_mwh': demanda_mwh,
            'hidro_mwh': hidro_mwh,
            'solar_mwh': solar_mwh,
            'eolica_mwh': eolica_mwh,
            'nuclear_mwh': GENERACION_NUCLEAR_MWH,
            'residual_mwh': residual_mwh,
            'coste_sistema_eur': coste_sistema_eur,
        })

tabla_resultados = pd.DataFrame(resultados)
salida = f"{OUTPUT_DIR}/electricity_cost.csv"
tabla_resultados.to_csv(salida, index=False)
print(f"Coste eléctrico finalizado: {salida}")
print(tabla_resultados.to_string(index=False))

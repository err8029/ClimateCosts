import pandas as pd
import streamlit as st

from common import load_header_title, load_logo

load_header_title()
load_logo()

RUTA = "electricity/output/electricity_cost.csv"
ESCENARIOS = {"RCP4.5": "rcp_4_5", "RCP8.5": "rcp_8_5"}


@st.cache_data
def cargar_datos():
    return pd.read_csv(RUTA)


st.title("⚡ Coste eléctrico adicional")
st.caption(
    "A diferencia del resto de riesgos, este indicador es **nacional, no municipal**: "
    "España tiene un único mercado eléctrico mayorista (MIBEL), así que no tiene sentido "
    "asignar un coste eléctrico por municipio - por eso esta página no tiene mapas. "
    "Modelo simplificado de 'orden de mérito': la demanda eléctrica proyectada menos la "
    "generación libre de combustible (hidráulica, solar, eólica) y el nuclear (fijo) es la "
    "'demanda residual' que hay que cubrir con centrales de ciclo combinado de gas (CCGT), "
    "la tecnología que casi siempre fija el precio marginal en España. El coste mostrado es "
    "esa demanda residual multiplicada por un precio de referencia del CCGT (90 €/MWh) - un "
    "proxy de orden de magnitud, no un modelo de despacho real. Ver README para fuentes y "
    "limitaciones."
)

etiqueta_escenario = st.selectbox("Escenario (RCP)", list(ESCENARIOS.keys()))
escenario = ESCENARIOS[etiqueta_escenario]

datos = cargar_datos()
datos_escenario = datos[datos['escenario'] == escenario].set_index('año')

metrica_2030, metrica_2050 = st.columns(2)
with metrica_2030:
    st.metric(
        "Coste adicional del sistema, 2030",
        f"{datos_escenario.loc[2030, 'coste_sistema_eur'] / 1e9:.2f} mil M€/año",
    )
with metrica_2050:
    incremento = datos_escenario.loc[2050, 'coste_sistema_eur'] - datos_escenario.loc[2030, 'coste_sistema_eur']
    st.metric(
        "Coste adicional del sistema, 2050",
        f"{datos_escenario.loc[2050, 'coste_sistema_eur'] / 1e9:.2f} mil M€/año",
        delta=f"{incremento / 1e9:+.2f} mil M€/año vs. 2030",
    )

st.subheader("Comparación entre escenarios y años")
comparacion = datos.copy()
comparacion['Escenario'] = comparacion['escenario'].map({'rcp_4_5': 'RCP4.5', 'rcp_8_5': 'RCP8.5'})
comparacion['Coste (mil M€/año)'] = comparacion['coste_sistema_eur'] / 1e9
tabla_comparacion = comparacion.pivot(index='año', columns='Escenario', values='Coste (mil M€/año)').round(2)
st.bar_chart(tabla_comparacion)

st.subheader("Desglose del balance eléctrico")
desglose = datos_escenario[['demanda_mwh', 'hidro_mwh', 'solar_mwh', 'eolica_mwh', 'nuclear_mwh', 'residual_mwh']].copy()
desglose = (desglose / 1e6).round(1)  # MWh -> TWh
desglose.columns = ['Demanda', 'Hidráulica', 'Solar', 'Eólica', 'Nuclear (fijo)', 'Residual (cubierto por gas)']
desglose.index.name = 'Año'
desglose = desglose.add_suffix(' (TWh/año)')
st.dataframe(desglose, width="stretch")

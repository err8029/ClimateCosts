"""Regenera todos los geojson que necesita la app (App.py + pages/*.py), ejecutando cada
script del pipeline en orden. Da feedback del progreso (paso X/N, % completado) mientras
avanza.

Requisitos previos que este script NO descarga por sí mismo (ver README):
- shared/boundaries/municipios_espana.* (descarga manual desde CNIG)
- flood/input/t10/, t100/, t500/ (descarga manual desde MITECO)
- Un .cdsapirc válido con credenciales de la API de Copernicus CDS

Uso: python regenerate_data.py
"""
import subprocess
import sys
import time
from pathlib import Path

PASOS = [
    ("Calor: descarga de datos", "heat/1_extract_data.py"),
    ("Calor: cálculo de riesgo", "heat/2_heatwave_risk.py"),
    ("Inundación: riesgo MITECO", "flood/3_flood_risk.py"),
    ("Inundación: descarga de caudal fluvial", "flood/4_extract_discharge_data.py"),
    ("Inundación: cálculo de riesgo de caudal", "flood/5_river_discharge_risk.py"),
    ("Sequía: descarga de datos", "drought/1_extract_data.py"),
    ("Sequía: cálculo de riesgo", "drought/2_drought_risk.py"),
    ("Incendios: descarga de datos", "wildfire/1_extract_data.py"),
    ("Incendios: cálculo de riesgo", "wildfire/2_wildfire_risk.py"),
    ("Riesgo combinado (25% cada hazard)", "combined/1_combined_risk.py"),
    ("Impacto financiero (proxy en euros)", "combined/2_financial_impact.py"),
]

REQUISITOS = [
    ("shared/boundaries/municipios_espana.shp", "Límites municipales (CNIG) - ver README, 'Getting the boundary data'"),
    ("flood/input/t10", "Shapefiles SNCZI T=10 años (MITECO) - ver README, 'Getting the flood data'"),
    ("flood/input/t100", "Shapefiles SNCZI T=100 años (MITECO) - ver README, 'Getting the flood data'"),
    ("flood/input/t500", "Shapefiles SNCZI T=500 años (MITECO) - ver README, 'Getting the flood data'"),
]


def comprobar_requisitos():
    faltantes = [(ruta, motivo) for ruta, motivo in REQUISITOS if not Path(ruta).exists()]
    if faltantes:
        print("Faltan datos de entrada que hay que descargar manualmente antes de continuar:\n")
        for ruta, motivo in faltantes:
            print(f"  - {ruta}\n    {motivo}")
        print("\nRellena esos datos y vuelve a ejecutar este script.")
        sys.exit(1)


def main():
    comprobar_requisitos()

    total = len(PASOS)
    inicio_total = time.time()

    for indice, (etiqueta, script) in enumerate(PASOS, start=1):
        porcentaje = round((indice - 1) / total * 100)
        print(f"\n[{indice}/{total}] ({porcentaje}%) {etiqueta} — {script}")
        print("-" * 70)

        inicio_paso = time.time()
        resultado = subprocess.run([sys.executable, script])
        duracion = time.time() - inicio_paso

        if resultado.returncode != 0:
            print(f"\n✗ Fallo en el paso {indice}/{total} ({script}), código de salida {resultado.returncode}.")
            print("Revisa el error de arriba, corrígelo, y vuelve a ejecutar este script "
                  "(los pasos anteriores ya completados no se repiten innecesariamente: "
                  "cada script se salta las descargas que ya existen).")
            sys.exit(resultado.returncode)

        print(f"✓ Paso {indice}/{total} completado en {duracion:.0f}s")

    duracion_total = time.time() - inicio_total
    print(f"\n[{total}/{total}] (100%) Regeneración completa en {duracion_total / 60:.1f} min.")
    print("La app ya puede ejecutarse: streamlit run App.py")


if __name__ == "__main__":
    main()

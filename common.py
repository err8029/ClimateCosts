"""Utilidades compartidas entre las páginas de la app (pages/*.py). No es una página en
sí misma - Streamlit solo convierte en página los ficheros pasados explícitamente a
st.Page() en App.py, así que este módulo no aparece en el menú de navegación."""
import geopandas as gpd
import pandas as pd
import streamlit as st
import leafmap.foliumap as leafmap
from branca.colormap import LinearColormap

CENTRO_ESPAÑA = (40, -3)
ZOOM_ESPAÑA = 5.5


@st.cache_data
def cargar_geojson(ruta):
    return gpd.read_file(ruta)


@st.cache_data
def rango_columna(rutas, columna):
    """Rango (min, max) de una columna a través de varios archivos/vistas, para que el
    color sea comparable entre ellas en vez de reescalarse cada vez (ver README)."""
    valores = pd.concat([cargar_geojson(r)[columna] for r in rutas])
    return float(valores.min()), float(valores.max())


def agregar_capa(m, ruta, columna, vmin, vmax, etiqueta=None, mostrar=True):
    """Añade una capa coloreada por `columna` a un mapa Folium ya existente `m`."""
    gdf = cargar_geojson(ruta).copy()

    colormap = LinearColormap(colors=['blue', 'green', 'yellow', 'orange', 'red'], vmin=vmin, vmax=vmax)
    colormap.caption = etiqueta or columna

    # Precalcular el color de cada municipio de una vez (aquí, con pandas) en vez de que
    # el style_function de folium llame a colormap() por cada una de las ~8000
    # geometrías al renderizar: es la optimización que más tiempo ahorra.
    gdf['color_hex'] = gdf[columna].apply(lambda v: colormap(v) if pd.notna(v) else '#808080')

    def style_function(feature):
        return {
            'fillColor': feature['properties']['color_hex'],
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.8,
        }

    m.add_gdf(
        gdf,
        layer_name=etiqueta or columna,
        style_function=style_function,
        zoom_to_layer=False,
        show=mostrar,
        fields=['NAMEUNIT', columna],
    )
    m.add_child(colormap)


@st.cache_resource
def construir_mapa(ruta, columna, vmin, vmax, etiqueta=None, centro=CENTRO_ESPAÑA, zoom=ZOOM_ESPAÑA):
    """Construye (y cachea) un mapa Folium de una sola capa, coloreada por `columna`.
    Cachear por los argumentos (ruta, columna, vmin, vmax...) evita reconstruir el mapa
    - el paso más lento de la app - cada vez que Streamlit vuelve a ejecutar el script
    tras cualquier interacción del usuario, incluso si ya se había visto exactamente
    esta combinación."""
    m = leafmap.Map(center=list(centro), zoom=zoom)
    agregar_capa(m, ruta, columna, vmin, vmax, etiqueta=etiqueta)
    return m


@st.cache_resource
def construir_mapa_combinado(capas, centro=CENTRO_ESPAÑA, zoom=ZOOM_ESPAÑA):
    """Construye (y cachea) un mapa Folium con varias capas superpuestas y control de
    capas (checkboxes) para poder activarlas/desactivarlas. `capas` es una lista de
    tuplas (ruta, columna, vmin, vmax, etiqueta, mostrar_por_defecto)."""
    m = leafmap.Map(center=list(centro), zoom=zoom)
    for ruta, columna, vmin, vmax, etiqueta, mostrar in capas:
        agregar_capa(m, ruta, columna, vmin, vmax, etiqueta=etiqueta, mostrar=mostrar)
    m.add_layer_control()
    return m

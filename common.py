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

LOGO = "assets/logo.png"


def load_logo():
    """Muestra el icono del globo (assets/logo.png, vía st.logo) y el texto "APOLLO"
    en blanco y negrita, uno junto al otro, en la cabecera de la barra lateral."""
    st.logo(LOGO, icon_image=LOGO, size="large")
    st.markdown(
        """
        <style>
        [data-testid="stSidebarHeader"] {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        [data-testid="stSidebarHeader"]::before {
            content: "APOLLO";
            order: 2;  /* el icono (renderizado por st.logo) ya ocupa el orden 0 por defecto */
            color: #ffffff;
            font-weight: bold;
            font-size: 22px;
            font-family: sans-serif;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    


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


def load_header_title():
    """Injects the 'Apollo' title, centered, into the top header bar (dark background,
    white text) - only that bar, not the rest of the page."""
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"] {
            background-color: #333333 !important;  /* Fondo gris oscuro, solo en la barra superior */
            position: relative;  /* Para que ::before se centre respecto a esta barra, no a un ancestro */
            z-index: 1000000 !important;  /* Por encima de la barra lateral en su borde compartido */
        }
        header[data-testid="stHeader"]::before {
            content: "v1.0.0";
            position: absolute;
            left: 90%;
            top: 50%;
            transform: translate(-20%, -50%);  /* Centrado horizontal y vertical */
            font-size: 18px;
            font-weight: bold;
            color: #ffffff !important;
            font-family: sans-serif;
            z-index: 999999;  /* Se mantiene por encima del resto de la barra */
        }
        /* El icono de hamburguesa (para abrir la barra lateral cuando está colapsada)
        vive dentro de esta misma barra oscura. Por defecto usa un gris tenue pensado
        para un fondo claro, así que aquí no se ve - se fuerza a blanco para que
        contraste, igual que el texto "Apollo". Es un icono de fuente (Material
        Symbols), no un <svg>, así que hay que forzar tanto `color` (el que realmente
        usa) como `fill` (por si acaso) en el botón y en todos sus hijos. */
        [data-testid="stExpandSidebarButton"],
        [data-testid="stExpandSidebarButton"] * {
            color: #ffffff !important;
            fill: #ffffff !important;
        }

        /* Barra lateral: mismo fondo oscuro que la cabecera, texto blanco en todo
        (enlaces de página, iconos, etc.) y las cabeceras de sección ("Por riesgo:",
        "Combinado:") en negrita. */
        [data-testid="stSidebar"] {
            background-color: #333333 !important;
            position: relative;  /* Para que z-index tenga efecto */
            z-index: 1 !important;  /* Explícitamente por debajo de la cabecera en toda su altura */
        }
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        [data-testid="stNavSectionHeader"] {
            font-weight: bold !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


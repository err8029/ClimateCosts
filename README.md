# ClimateCosts

Modeling the impact of climate change — heat, flooding, wildfire, and drought — on every municipality in Spain, using official climate and hazard data, for visualization in QGIS.

## Status

Work in progress, scaling up from an initial Comunidad de Madrid pilot to national coverage. Currently implemented: nationwide heat-mortality risk (temperature exposure + population). Flood, wildfire, and drought indicators are planned next; see [Next steps](#next-steps).

## Approach

Each hazard is modeled independently and stored as its own indicator column(s) on the national municipal boundary layer, rather than blended into a single score — so each can be toggled and styled separately in QGIS. Where an official hazard dataset exists (flood zones, fire history, drought indices), that's used in preference to deriving risk purely from raw climate projections.

| Hazard | Source |
|---|---|
| Heat-mortality | Copernicus CMIP6 (`tasmax`) + INE municipal population (Padrón) |
| Flood | MITECO SNCZI flood-zone maps by return period *(planned)* |
| Drought | SPEI Global Drought Monitor (CSIC) *(planned)* |
| Wildfire | EFFIS historical burnt-area perimeters *(planned)* |

## Pipeline

### 1. `1_extract_data.py` — Download climate projections
Downloads CMIP6 climate projection data from the Copernicus Climate Data Store (CDS), covering peninsular Spain and the Balearic Islands, for the year 2030 under the SSP2-4.5 emissions scenario: daily maximum near-surface air temperature for the summer months (heat-mortality risk).

Requires a valid `.cdsapirc` file with Copernicus CDS API credentials (not tracked in this repo).

### 2. `2_zonify_data.py` — Heat-mortality risk by municipality
Loads the national municipal boundaries (`municipios_espana.shp`, from CNIG) and, for every municipality:
- Clips the CMIP6 temperature raster to compute `temp_max_verano` (mean summer max temperature).
- Fetches current population from INE's official Padrón municipal population table (via the public INE API) as `poblacion`.
- Combines both, each normalized 0–1 (population log-scaled, since it's heavily skewed), into `heat_mortality_risk` — a **relative proxy** for heat-mortality burden, not a literal death count.

Output: `municipios_calor_2030.geojson`.

**Known limitations**:
- The CMIP6 model used (GFDL-ESM4) has a coarse ~100km grid, so many neighboring municipalities share the same temperature value — the resulting map has a "blocky" look rather than fine local detail. A higher-resolution regional dataset (e.g. EURO-CORDEX) would be a future improvement.
- ~88 polygons in the CNIG boundary set are "Comunidades de Villa y Tierra" / mancomunidades (historic communal land-management entities), not real inhabited municipalities, so they have no INE population figure and are left with a null `heat_mortality_risk`. This is expected, not a bug.

## Data

- `municipios_espana.*` — national municipal boundary shapefile (CNIG, "Líneas Límite Municipales"), not tracked in git (see [Getting the boundary data](#getting-the-boundary-data)).
- `temperaturas_2030.zip` / `.nc` — raw Copernicus CMIP6 temperature download.
- `municipios_calor_2030.geojson` — municipalities with the heat-mortality risk indicator attached.
- `madrid_buildings.gpkg` — Madrid building footprints (for future building-level cost/exposure analysis).
- `QGIS/` — QGIS project files for visualizing the data.

Large/generated data files, boundary shapefiles, and API credentials are excluded from version control (see `.gitignore`) — they're either downloaded by the scripts above or fetched manually as described below.

### Getting the boundary data

Download "Líneas Límite Municipales" (national municipal boundaries) from the [CNIG Download Center](https://centrodedescargas.cnig.es/CentroDescargas/limites-municipales-provinciales-autonomicos), free of charge. Extract the `recintos_municipales_inspire_peninbal_etrs89` shapefile (peninsula + Balearics) from the `SHP_ETRS89` folder and place its files in the project root, renamed to `municipios_espana.*`. (The Canary Islands boundary set, in a different CRS, is handled separately — not yet wired into the pipeline.)

## Requirements

- Python 3
- [`cdsapi`](https://pypi.org/project/cdsapi/) (Copernicus CDS API client)
- `geopandas`
- `xarray`
- `rioxarray`
- `netCDF4`
- `requests`
- `numpy`

## Next steps

- Add flood risk from MITECO's SNCZI flood-zone maps (% of municipal area in each return-period flood zone).
- Add drought risk from the SPEI Global Drought Monitor, using the same raster-clip-per-municipality approach as the heat script.
- Add wildfire risk from EFFIS historical burnt-area data.
- Merge all hazard indicators into a single national GeoPackage plus a styled QGIS project.
- Translate hazard indicators into estimated economic costs per municipality.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

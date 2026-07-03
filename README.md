# ClimateCosts

Estimating the local economic and human costs of climate change (heatwaves, flooding) for municipalities in the Comunidad de Madrid, using climate projection data from Copernicus (CMIP6).

## Status

Work in progress. The pipeline currently covers data extraction and spatial zonification; cost estimation itself is not yet implemented.

## Pipeline

### 1. `1_extract_data.py` — Download climate projections
Downloads CMIP6 climate projection data from the Copernicus Climate Data Store (CDS) for the Madrid region, for the year 2030 under the SSP2-4.5 emissions scenario:
- **Temperature**: daily maximum near-surface air temperature (summer months, for heat-related mortality risk).
- **Precipitation**: daily accumulated precipitation (full year, for flood risk).

Requires a valid `.cdsapirc` file with Copernicus CDS API credentials (not tracked in this repo).

### 2. `2_zonify_data.py` — Zonify climate data by municipality
Loads the Comunidad de Madrid municipal boundaries (`municipios_comunidad.shp`) and clips/aggregates the downloaded NetCDF climate rasters to each municipality, producing per-municipality climate indicators:
- `temp_max_verano`: average summer maximum temperature.
- `precip_max_24h`: extreme 24h precipitation indicator.

Output: `municipios_con_clima_2030.geojson`, ready for downstream cost analysis.

## Data

- `municipios_comunidad.*` — municipal boundary shapefile for the Comunidad de Madrid.
- `temperaturas_2030.zip` / `precipitaciones_2030.zip` (+ extracted `.nc` files) — raw Copernicus climate data downloads.
- `municipios_con_clima_2030.geojson` — municipalities with attached 2030 climate indicators.
- `madrid_buildings.gpkg` — building footprints for Madrid (for future building-level cost/exposure analysis).
- `QGIS/` — QGIS project files for visualizing the data.

Large/generated data files and API credentials are excluded from version control (see `.gitignore`).

## Requirements

- Python 3
- [`cdsapi`](https://pypi.org/project/cdsapi/) (Copernicus CDS API client)
- `geopandas`
- `xarray`
- `rioxarray`
- `netCDF4`

## Next steps

- Translate climate indicators (heat, precipitation extremes) into estimated economic and human costs per municipality.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

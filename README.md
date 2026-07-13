# ClimateCosts

Modeling the impact of climate change — heat, flooding, wildfire, and drought — on every municipality in Spain, using official climate and hazard data, for visualization in QGIS.

## Status

Work in progress, scaling up from an initial Comunidad de Madrid pilot to national coverage. Currently implemented: nationwide heat-mortality risk (temperature exposure + population) and flood risk (population affected by return-period flood zones). Wildfire and drought indicators are planned next; see [Next steps](#next-steps).

## Approach

Each hazard is modeled independently and stored as its own indicator column(s) on the national municipal boundary layer, rather than blended into a single score — so each can be toggled and styled separately in QGIS. Where an official hazard dataset exists (flood zones, fire history, drought indices), that's used in preference to deriving risk purely from raw climate projections.

| Hazard | Source |
|---|---|
| Heat-mortality | Copernicus C3S EURO-CORDEX-derived temperature statistics (max + min) + raw CORDEX humidity (Heat Index) + INE municipal population (Padrón) |
| Flood | MITECO SNCZI "riesgo de población" flood-risk maps, T=10/100/500yr return periods |
| Drought | SPEI Global Drought Monitor (CSIC) *(planned)* |
| Wildfire | EFFIS historical burnt-area perimeters *(planned)* |

## Pipeline

### 1. `1_extract_data.py` — Download climate projections
Downloads two things from the Copernicus Climate Data Store (CDS):
- **Temperature**: bias-adjusted EURO-CORDEX temperature statistics — 30-year-smoothed summer average maximum and minimum temperature, RCP4.5, ~0.1° (~11km) resolution across Europe. This API doesn't support filtering by area or year, so the script downloads the full 1986–2085 European timeseries and slices it locally with `xarray` down to peninsular Spain + Balearics and the year 2030. Output: `temperaturas_2030_eurocordex.nc` (variables `mean_Tmax_Summer`, `mean_Tmin_Summer`, °C).
- **Humidity**: raw daily relative humidity (`hurs`) from a single EURO-CORDEX regional run (driving GCM MOHC-HadGEM2-ES, RCM SMHI-RCA4, r1i1p1, RCP4.5, EUR-11 ~0.11° domain) for JJA 2030 over Spain, averaged locally into one summer-mean value per grid cell. Needed to compute a Heat Index (temperature alone understates perceived/physiological heat stress when humidity is high). Output: `humedad_2030_eurocordex.nc` (variable `hurs`, %).

Requires a valid `.cdsapirc` file with Copernicus CDS API credentials (not tracked in this repo), and accepting each dataset's license once (linked from the 403 error the first time you run it if not yet accepted): [sis-temperature-statistics](https://cds.climate.copernicus.eu/datasets/sis-temperature-statistics?tab=download#manage-licences), [projections-cordex-domains-single-levels](https://cds.climate.copernicus.eu/datasets/projections-cordex-domains-single-levels?tab=download#manage-licences).

**Known limitation**: the temperature data is a multi-model **ensemble mean**, while the humidity data is from a **single** GCM-RCM run (no equivalent pre-processed multi-model humidity product exists) — combining them is a reasonable approximation for a relative risk proxy, but not fully consistent methodologically.

### 2. `2_heatwave_risk.py` — Heat-mortality risk by municipality
Loads the national municipal boundaries (`municipios_espana.shp`, from CNIG) and, for every municipality:
- Clips the EURO-CORDEX temperature raster (plain lat/lon grid) to get `temp_max_verano_c` and `temp_min_verano_c` (mean summer max/min temperature).
- Clips the CORDEX humidity raster to get `humedad_verano_pct` (mean summer relative humidity). This raster uses a **rotated-pole grid** (`rlon`/`rlat`, not real lat/lon) — its CRS is reconstructed with `pyproj.CRS.from_cf()` from the `rotated_pole` grid-mapping variable, and municipality centroids are transformed into rotated coordinates for the small-municipality nearest-point fallback.
- Computes a **Heat Index** (NWS/Rothfusz formula, temperature + humidity) separately for daytime (`heat_index_max_c`, from max temp) and nighttime (`heat_index_min_c`, from min temp — capturing "noches tropicales", tropical nights that don't cool enough for the body to recover, made worse by humidity).
- Fetches current population from INE's official Padrón municipal population table (via the public INE API) as `poblacion`.
- Combines `heat_index_max_c` and `heat_index_min_c` in equal parts (50/50) into a single heat-exposure score, each normalized 0–1; then averages that exposure score with population (50/50, population log-scaled since it's heavily skewed) into `heat_mortality_risk` — a **relative proxy** for heat-mortality burden, not a literal death count.

Output: `municipios_heatwave_risk.geojson`.

**Known limitations**:
- `mean_Tmin_Summer`/`humedad_verano_pct` are 30-year-smoothed/seasonal *averages*, not literal tropical-night counts — used as continuous stand-ins for "how tropical the nights are", not a literal tally.
- ~33 small coastal municipalities (Basque/Cantabria coast, Ibiza) and North African exclaves (Melilla, Chafarinas, Alhucemas, Vélez de la Gomera) have no temperature value: the EURO-CORDEX grid masks out ocean cells, and these municipalities' polygons — and their nearest grid point — fall on masked cells. Not a bug, just outside this dataset's land coverage.
- ~88 polygons in the CNIG boundary set are "Comunidades de Villa y Tierra" / mancomunidades (historic communal land-management entities), not real inhabited municipalities, so they have no INE population figure and are left with a null `heat_mortality_risk`. This is expected, not a bug.

### 3. `3_flood_risk.py` — Flood risk by municipality
Loads three MITECO SNCZI "riesgo de población" shapefiles (Peninsula + Balearics, return periods T=10/100/500 years). These already come with per-municipality attributes (`NUM_AFE_MU` = people affected, `N_HAB_MUNI` = reference population), so no geometric overlay is needed — just an attribute join by municipality code. For each return period, computes `flood_risk_tXX` (fraction of the municipality's reference population in a flood-risk zone, clipped to [0, 1]) and `flood_risk_tXX_poblacion_afectada` (raw affected-population count).

Output: `municipios_inundacion.geojson`.

Requires the three SNCZI shapefiles extracted under `flood_raw/t10/`, `flood_raw/t100/`, `flood_raw/t500/` (see [Getting the flood data](#getting-the-flood-data)).

**Known limitation**: `N_HAB_MUNI` is MITECO's own reference population from the SNCZI study (not the current INE figure used elsewhere in this project), so `flood_risk_tXX` fractions are internally consistent within the flood dataset but not on exactly the same population vintage as `heat_mortality_risk`.

## Data

- `municipios_espana.*` — national municipal boundary shapefile (CNIG, "Líneas Límite Municipales"), not tracked in git (see [Getting the boundary data](#getting-the-boundary-data)).
- `summer_max_min.zip` / `sis_temp_raw/` / `temperaturas_2030_eurocordex.nc` — raw and processed Copernicus EURO-CORDEX temperature download.
- `humedad_2030.zip` / `cordex_humedad_raw/` / `humedad_2030_eurocordex.nc` — raw and processed CORDEX humidity download.
- `municipios_heatwave_risk.geojson` — municipalities with the heat-mortality risk indicator attached.
- `flood_raw/t10/`, `flood_raw/t100/`, `flood_raw/t500/` — raw SNCZI flood-risk shapefiles, not tracked in git (see [Getting the flood data](#getting-the-flood-data)).
- `municipios_inundacion.geojson` — municipalities with flood risk indicators attached.
- `madrid_buildings.gpkg` — Madrid building footprints (for future building-level cost/exposure analysis).
- `QGIS/` — QGIS project files for visualizing the data.

Large/generated data files, boundary shapefiles, and API credentials are excluded from version control (see `.gitignore`) — they're either downloaded by the scripts above or fetched manually as described below.

### Getting the boundary data

Download "Líneas Límite Municipales" (national municipal boundaries) from the [CNIG Download Center](https://centrodedescargas.cnig.es/CentroDescargas/limites-municipales-provinciales-autonomicos), free of charge. Extract the `recintos_municipales_inspire_peninbal_etrs89` shapefile (peninsula + Balearics) from the `SHP_ETRS89` folder and place its files in the project root, renamed to `municipios_espana.*`. (The Canary Islands boundary set, in a different CRS, is handled separately — not yet wired into the pipeline.)

### Getting the flood data

Download the "riesgo de población" (risk to population) shapefiles for Peninsula + Baleares from MITECO, one per return period (these are click-through downloads, not stable direct-download URLs):
- [T=10 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t10.html) (~300MB)
- [T=100 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t100.html) (~390MB)
- [T=500 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t500.html) (~370MB)

Extract each into `flood_raw/t10/`, `flood_raw/t100/`, `flood_raw/t500/` respectively. Free to use with MITECO attribution.

## Requirements

- Python 3
- [`cdsapi`](https://pypi.org/project/cdsapi/) (Copernicus CDS API client)
- `geopandas`
- `xarray`
- `rioxarray`
- `netCDF4`
- `requests`
- `numpy`
- `pyogrio`
- `pyproj`

## Next steps

- Add drought risk from the SPEI Global Drought Monitor, using the same raster-clip-per-municipality approach as the heat script.
- Add wildfire risk from EFFIS historical burnt-area data.
- Merge all hazard indicators into a single national GeoPackage plus a styled QGIS project.
- Translate hazard indicators into estimated economic costs per municipality.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

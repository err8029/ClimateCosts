# ClimateCosts

Modeling the impact of climate change — heat, flooding, wildfire, and drought — on every municipality in Spain, using official climate and hazard data, for visualization in QGIS.

## Status

Work in progress, scaling up from an initial Comunidad de Madrid pilot to national coverage. Currently implemented: nationwide heat-mortality risk (Heat Index from temperature + humidity, weighted by population, across 2 years × 2 emissions scenarios) and flood risk (population affected by return-period flood zones), plus a Streamlit map viewer (`App.py`). Wildfire and drought indicators are planned next; see [Next steps](#next-steps).

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
Downloads, for every combination of **year** (2030, 2050) **× scenario** (RCP4.5, RCP8.5), two things from the Copernicus Climate Data Store (CDS):
- **Temperature**: bias-adjusted EURO-CORDEX temperature statistics — 30-year-smoothed summer average maximum and minimum temperature, ~0.1° (~11km) resolution across Europe. This API doesn't support filtering by area or year (but does let you pick the scenario), so the script downloads the full 1986–2085 European timeseries **once per scenario** and slices it locally with `xarray` down to peninsular Spain + Balearics and each year. Output: `temperaturas_{año}_{escenario}_eurocordex.nc` (variables `mean_Tmax_Summer`, `mean_Tmin_Summer`, °C).
- **Humidity**: raw daily relative humidity (`hurs`) from a single EURO-CORDEX regional run (driving GCM MOHC-HadGEM2-ES, RCM SMHI-RCA4, r1i1p1, EUR-11 ~0.11° domain) for JJA of the given year, averaged locally into one summer-mean value per grid cell. Needed to compute a Heat Index (temperature alone understates perceived/physiological heat stress when humidity is high). This API *does* support filtering by year/scenario/area, so it's one download per year×scenario combination (4 total). Output: `humedad_{año}_{escenario}_eurocordex.nc` (variable `hurs`, %).

Requires a valid `.cdsapirc` file with Copernicus CDS API credentials (not tracked in this repo), and accepting each dataset's license once (linked from the 403 error the first time you run it if not yet accepted): [sis-temperature-statistics](https://cds.climate.copernicus.eu/datasets/sis-temperature-statistics?tab=download#manage-licences), [projections-cordex-domains-single-levels](https://cds.climate.copernicus.eu/datasets/projections-cordex-domains-single-levels?tab=download#manage-licences).

**Known limitation**: the temperature data is a multi-model **ensemble mean**, while the humidity data is from a **single** GCM-RCM run (no equivalent pre-processed multi-model humidity product exists) — combining them is a reasonable approximation for a relative risk proxy, but not fully consistent methodologically. Also note "RCP4.5/RCP8.5" (CMIP5-era scenario naming, used by EURO-CORDEX) isn't the same thing as "SSP" (CMIP6-era naming) — there's no direct 1:1 mapping, they're just the closest equivalent available at this resolution.

### 2. `2_heatwave_risk.py` — Heat-mortality risk by municipality
Loads the national municipal boundaries (`municipios_espana.shp`, from CNIG) once, fetches population once (see below), then for **each of the 4 year×scenario combinations** and for every municipality:
- Clips the EURO-CORDEX temperature raster (plain lat/lon grid) to get `temp_max_verano_c` and `temp_min_verano_c` (mean summer max/min temperature).
- Clips the CORDEX humidity raster to get `humedad_verano_pct` (mean summer relative humidity). This raster uses a **rotated-pole grid** (`rlon`/`rlat`, not real lat/lon) — its CRS is reconstructed with `pyproj.CRS.from_cf()` from the `rotated_pole` grid-mapping variable, and municipality centroids are transformed into rotated coordinates for the small-municipality nearest-point fallback.
- Computes a **Heat Index** (NWS/Rothfusz formula, temperature + humidity) separately for daytime (`heat_index_max_c`, from max temp) and nighttime (`heat_index_min_c`, from min temp — capturing "noches tropicales", tropical nights that don't cool enough for the body to recover, made worse by humidity).
- Combines `heat_index_max_c` and `heat_index_min_c` in equal parts (50/50) into a single heat-exposure score, each normalized 0–1; then averages that exposure score with population (50/50, population log-scaled since it's heavily skewed) into `heat_mortality_risk` — a **relative proxy** for heat-mortality burden, not a literal death count.

Population comes from INE's official Padrón municipal population table (via the public INE API) and doesn't vary by year/scenario, so it's fetched once and reused across all 4 combinations.

Output: `municipios_heatwave_risk_{año}_{escenario}.geojson` (full, all columns) and `municipios_heatwave_risk_{año}_{escenario}_lite.geojson` (just `NAMEUNIT` + the 3 columns the app actually displays, with geometry simplified to a 0.001° / ~111m tolerance). The lite version is what `App.py` loads — dropping columns barely changes file size (geometry dominates), but simplifying geometry cuts it by ~90% (134MB → ~15MB) with no visible difference at national/city map zoom levels.

**Known limitations**:
- `mean_Tmin_Summer`/`humedad_verano_pct` are 30-year-smoothed/seasonal *averages*, not literal tropical-night counts — used as continuous stand-ins for "how tropical the nights are", not a literal tally.
- ~33 small coastal municipalities (Basque/Cantabria coast, Ibiza) and North African exclaves (Melilla, Chafarinas, Alhucemas, Vélez de la Gomera) have no temperature value: the EURO-CORDEX grid masks out ocean cells, and these municipalities' polygons — and their nearest grid point — fall on masked cells. Not a bug, just outside this dataset's land coverage.
- ~88 polygons in the CNIG boundary set are "Comunidades de Villa y Tierra" / mancomunidades (historic communal land-management entities), not real inhabited municipalities, so they have no INE population figure and are left with a null `heat_mortality_risk`. This is expected, not a bug.

### `App.py` — Interactive map (Streamlit)
A Streamlit + leafmap viewer showing **two side-by-side maps** — 2030 (left) and 2050 (right) — for the lite geojsons, with **Escenario (SSP/RCP)** and **Variable** dropdowns (variable = riesgo de mortalidad por calor, índice de calor diurno, or índice de calor nocturno). The color scale (`vmin`/`vmax`) is fixed per variable across both years and both scenarios (not recomputed per view), so color is visually comparable when switching selections — mixing scales across variables wouldn't make sense, since `heat_mortality_risk` is 0–1 while the Heat Index columns are in °C. Municipalities with a null value (see known limitations above) render gray instead of crashing the colormap.

Below the maps, a table lists the **top 10 municipalities by 2030→2050 increment** for the selected scenario/variable — joined by `ine_code` (not name: 17 municipality names repeat nationally, e.g. two different "Mieres", so a name-only join would silently merge unrelated municipalities).

Run with `streamlit run App.py` (or `python -m streamlit run App.py` if the `streamlit` command isn't on your PATH).

### 3. `3_flood_risk.py` — Flood risk by municipality
Loads three MITECO SNCZI "riesgo de población" shapefiles (Peninsula + Balearics, return periods T=10/100/500 years). These already come with per-municipality attributes (`NUM_AFE_MU` = people affected, `N_HAB_MUNI` = reference population), so no geometric overlay is needed — just an attribute join by municipality code. For each return period, computes `flood_risk_tXX` (fraction of the municipality's reference population in a flood-risk zone, clipped to [0, 1]) and `flood_risk_tXX_poblacion_afectada` (raw affected-population count).

Output: `municipios_inundacion.geojson`.

Requires the three SNCZI shapefiles extracted under `flood_raw/t10/`, `flood_raw/t100/`, `flood_raw/t500/` (see [Getting the flood data](#getting-the-flood-data)).

**Known limitation**: `N_HAB_MUNI` is MITECO's own reference population from the SNCZI study (not the current INE figure used elsewhere in this project), so `flood_risk_tXX` fractions are internally consistent within the flood dataset but not on exactly the same population vintage as `heat_mortality_risk`.

## Data

- `municipios_espana.*` — national municipal boundary shapefile (CNIG, "Líneas Límite Municipales"), not tracked in git (see [Getting the boundary data](#getting-the-boundary-data)).
- `summer_max_min_{escenario}.zip` / `sis_temp_raw_{escenario}/` / `temperaturas_{año}_{escenario}_eurocordex.nc` — raw and processed Copernicus EURO-CORDEX temperature download (one raw download per scenario, one processed file per year×scenario).
- `humedad_{año}_{escenario}.zip` / `cordex_humedad_raw_{año}_{escenario}/` / `humedad_{año}_{escenario}_eurocordex.nc` — raw and processed CORDEX humidity download (one per year×scenario).
- `municipios_heatwave_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the heat-mortality risk indicators attached (full and app-optimized versions), one pair per year×scenario combination.
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
- `streamlit`
- `leafmap`
- `branca`
- `pandas`

## Next steps

- Add drought risk from the SPEI Global Drought Monitor, using the same raster-clip-per-municipality approach as the heat script.
- Add wildfire risk from EFFIS historical burnt-area data.
- Merge all hazard indicators into a single national GeoPackage plus a styled QGIS project.
- Translate hazard indicators into estimated economic costs per municipality.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

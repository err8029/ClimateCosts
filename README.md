# ClimateCosts

Modeling the impact of climate change — heat, flooding, wildfire, and drought — on every municipality in Spain, using official climate and hazard data, for visualization in QGIS.

## Status

Work in progress, scaling up from an initial Comunidad de Madrid pilot to national coverage. Currently implemented: nationwide heat-mortality risk (Heat Index from temperature + humidity, weighted by population, across 2 years × 2 emissions scenarios) and flood risk (population affected by return-period flood zones), plus a multi-page Streamlit app (`App.py` + `pages/`) with a sidebar-navigable page per hazard and a combined multi-layer view. Wildfire and drought indicators are planned next; see [Next steps](#next-steps).

## Approach

Each hazard is modeled independently and stored as its own indicator column(s) on the national municipal boundary layer, rather than blended into a single score — so each can be toggled and styled separately in QGIS. Where an official hazard dataset exists (flood zones, fire history, drought indices), that's used in preference to deriving risk purely from raw climate projections.

| Hazard | Source |
|---|---|
| Heat-mortality | Copernicus C3S EURO-CORDEX-derived temperature statistics (max + min) + raw CORDEX humidity (Heat Index) + INE municipal population, projected to 2030/2050 via provincial growth rates |
| Flood | MITECO SNCZI "riesgo de población" flood-risk maps, T=10/100/500yr return periods |
| Drought | SPEI Global Drought Monitor (CSIC) *(planned)* |
| Wildfire | EFFIS historical burnt-area perimeters *(planned)* |

## Project structure

Each hazard is a self-contained folder with its own scripts, raw downloads, generated outputs, and QGIS project:

```
ClimateCosts/
├── App.py                    # Streamlit entry point: st.navigation router only
├── common.py                  # Shared map-building/caching helpers used by pages/*.py
├── pages/
│   ├── heat.py                 # Heat-mortality risk page
│   ├── flood.py                 # Flood risk page
│   ├── drought.py                # Placeholder ("not implemented yet")
│   ├── wildfire.py                # Placeholder ("not implemented yet")
│   └── combined.py                 # Multi-hazard overlay (toggleable layers)
├── test_app.py                # pytest suite for the whole app
├── shared/
│   └── boundaries/            # National municipal boundary shapefile (CNIG), shared by every hazard
├── heat/
│   ├── 1_extract_data.py      # Downloads CMIP6/EURO-CORDEX temperature + humidity
│   ├── 2_heatwave_risk.py     # Computes heat_mortality_risk per municipality
│   ├── input/                 # Raw CDS downloads + extracted/processed NetCDFs
│   ├── output/                 # municipios_heatwave_risk_{año}_{escenario}(.geojson|_lite.geojson)
│   └── QGIS/
├── flood/
│   ├── 3_flood_risk.py
│   ├── input/                  # Raw SNCZI shapefiles (t10/t100/t500)
│   ├── output/                 # municipios_inundacion(.geojson|_lite.geojson)
│   └── QGIS/
├── drought/                    # input/, output/, QGIS/ — not implemented yet
└── wildfire/                   # input/, output/, QGIS/ — not implemented yet
```

All scripts are written to run from the repository root (e.g. `python heat/2_heatwave_risk.py`, not from inside `heat/`), and read/write paths accordingly.

## Pipeline

### 1. `heat/1_extract_data.py` — Download climate projections
Downloads, for every combination of **year** (2030, 2050) **× scenario** (RCP4.5, RCP8.5), two things from the Copernicus Climate Data Store (CDS):
- **Temperature**: bias-adjusted EURO-CORDEX temperature statistics — 30-year-smoothed summer average maximum and minimum temperature, ~0.1° (~11km) resolution across Europe. This API doesn't support filtering by area or year (but does let you pick the scenario), so the script downloads the full 1986–2085 European timeseries **once per scenario** and slices it locally with `xarray` down to peninsular Spain + Balearics and each year. Output: `heat/input/temperaturas_{año}_{escenario}_eurocordex.nc` (variables `mean_Tmax_Summer`, `mean_Tmin_Summer`, °C).
- **Humidity**: raw daily relative humidity (`hurs`) from a single EURO-CORDEX regional run (driving GCM MOHC-HadGEM2-ES, RCM SMHI-RCA4, r1i1p1, EUR-11 ~0.11° domain) for JJA of the given year, averaged locally into one summer-mean value per grid cell. Needed to compute a Heat Index (temperature alone understates perceived/physiological heat stress when humidity is high). This API *does* support filtering by year/scenario/area, so it's one download per year×scenario combination (4 total). Output: `heat/input/humedad_{año}_{escenario}_eurocordex.nc` (variable `hurs`, %).

Requires a valid `.cdsapirc` file with Copernicus CDS API credentials (not tracked in this repo), and accepting each dataset's license once (linked from the 403 error the first time you run it if not yet accepted): [sis-temperature-statistics](https://cds.climate.copernicus.eu/datasets/sis-temperature-statistics?tab=download#manage-licences), [projections-cordex-domains-single-levels](https://cds.climate.copernicus.eu/datasets/projections-cordex-domains-single-levels?tab=download#manage-licences).

**Known limitation**: the temperature data is a multi-model **ensemble mean**, while the humidity data is from a **single** GCM-RCM run (no equivalent pre-processed multi-model humidity product exists) — combining them is a reasonable approximation for a relative risk proxy, but not fully consistent methodologically. Also note "RCP4.5/RCP8.5" (CMIP5-era scenario naming, used by EURO-CORDEX) isn't the same thing as "SSP" (CMIP6-era naming) — there's no direct 1:1 mapping, they're just the closest equivalent available at this resolution.

### 2. `heat/2_heatwave_risk.py` — Heat-mortality risk by municipality
Loads the national municipal boundaries (`shared/boundaries/municipios_espana.shp`, from CNIG) once, then:

**Population projection.** INE doesn't publish population projections at municipality level — only down to *province*, and even then only for 2026–2041 (national-only projections run to 2076, but with no geographic breakdown at all). So: fetch each province's real projected growth factor for 2030 from INE table 36725 and apply it to every municipality in that province; for 2050 (outside the published 2026–2041 range), extrapolate the same annualized growth rate observed over 2026–2041 nine more years. This is applied per-province, so growing provinces (e.g. Guadalajara, +19% by 2041) and shrinking ones (e.g. Zamora, −8%) get genuinely different trajectories — it's not a single national multiplier.

**Per year×scenario** (4 combinations), and for every municipality:
- Clips the EURO-CORDEX temperature raster (plain lat/lon grid) to get `temp_max_verano_c` and `temp_min_verano_c` (mean summer max/min temperature).
- Clips the CORDEX humidity raster to get `humedad_verano_pct` (mean summer relative humidity). This raster uses a **rotated-pole grid** (`rlon`/`rlat`, not real lat/lon) — its CRS is reconstructed with `pyproj.CRS.from_cf()` from the `rotated_pole` grid-mapping variable, and municipality centroids are transformed into rotated coordinates for the small-municipality nearest-point fallback.
- Computes a **Heat Index** (NWS/Rothfusz formula, temperature + humidity) separately for daytime (`heat_index_max_c`, from max temp) and nighttime (`heat_index_min_c`, from min temp — capturing "noches tropicales", tropical nights that don't cool enough for the body to recover, made worse by humidity).
- Combines `heat_index_max_c`, `heat_index_min_c`, and projected population (log-scaled, since it's heavily skewed) in **equal thirds (33.3% each)** into `heat_mortality_risk` — a **relative proxy** for heat-mortality burden, not a literal death count.

All three components are normalized 0–1 using a **fixed range computed once across all 4 year×scenario combinations** (not recomputed per year). This matters: if you min-max normalize each year independently, `heat_mortality_risk` stops reflecting actual warming/demographic change and instead reflects only that year's *relative* ranking — a municipality can get objectively hotter and more populous and still see its score *drop*, if other municipalities changed even faster. Normalizing against one fixed range lets the score properly track change over time. (Earlier versions of this project had exactly that bug — verified while investigating why the biggest cities showed near-zero or negative 2030→2050 deltas despite clearly warming; some also showed a shrinking population *and* a rising score simultaneously, once fixed, before the fix nothing added up.)

Output: `heat/output/municipios_heatwave_risk_{año}_{escenario}.geojson` (full, all columns) and `heat/output/municipios_heatwave_risk_{año}_{escenario}_lite.geojson` (just `NAMEUNIT` + the 3 columns the app actually displays, with geometry simplified to a 0.001° / ~111m tolerance). The lite version is what `App.py` loads — dropping columns barely changes file size (geometry dominates), but simplifying geometry cuts it by ~90% (134MB → ~15MB) with no visible difference at national/city map zoom levels.

**Known limitations**:
- Population projections beyond 2041 (i.e. the 2050 figures) are a linear extrapolation of each province's own 2026–2041 trend, not an official INE projection — nobody publishes municipal, or even provincial, population projections that far out.
- `mean_Tmin_Summer`/`humedad_verano_pct` are 30-year-smoothed/seasonal *averages*, not literal tropical-night counts — used as continuous stand-ins for "how tropical the nights are", not a literal tally.
- ~33 small coastal municipalities (Basque/Cantabria coast, Ibiza) and North African exclaves (Melilla, Chafarinas, Alhucemas, Vélez de la Gomera) have no temperature value: the EURO-CORDEX grid masks out ocean cells, and these municipalities' polygons — and their nearest grid point — fall on masked cells. Not a bug, just outside this dataset's land coverage.
- ~88 polygons in the CNIG boundary set are "Comunidades de Villa y Tierra" / mancomunidades (historic communal land-management entities), not real inhabited municipalities, so they have no INE population figure and are left with a null `heat_mortality_risk`. This is expected, not a bug.

### 3. `flood/3_flood_risk.py` — Flood risk by municipality
Loads three MITECO SNCZI "riesgo de población" shapefiles (Peninsula + Balearics, return periods T=10/100/500 years). These already come with per-municipality attributes (`NUM_AFE_MU` = people affected, `N_HAB_MUNI` = reference population), so no geometric overlay is needed — just an attribute join by municipality code. For each return period, computes `flood_risk_tXX` (fraction of the municipality's reference population in a flood-risk zone, clipped to [0, 1]) and `flood_risk_tXX_poblacion_afectada` (raw affected-population count).

**2030/2050 population projection.** Spain has no official future flood-extent maps — SNCZI's zones are fixed present-day hazard geography, not climate-projected. So rather than projecting the flood zones themselves (not possible with available data), this projects *how many people* would be exposed to that same fixed physical risk: the same INE provincial growth-factor approach used for heat (real 2030 figures, 2050 extrapolated from the 2026–2041 trend) is applied directly to each return period's affected-population count, giving `flood_risk_tXX_poblacion_afectada_2030` and `_2050`. The `flood_risk_tXX` fraction itself is left unprojected/unchanged, since it's the fixed hazard geography, not the demographic exposure to it.

Output: `flood/output/municipios_inundacion.geojson` (full) and `flood/output/municipios_inundacion_lite.geojson` (the `flood_risk_tXX` + affected-population columns, current and projected, + simplified geometry, same rationale as the heat lite files — `pages/flood.py` loads this one).

Requires the three SNCZI shapefiles extracted under `flood/input/t10/`, `flood/input/t100/`, `flood/input/t500/` (see [Getting the flood data](#getting-the-flood-data)).

**Known limitations**:
- `N_HAB_MUNI` is MITECO's own reference population from the SNCZI study (not the current INE figure used elsewhere in this project), so `flood_risk_tXX` fractions are internally consistent within the flood dataset but not on exactly the same population vintage as `heat_mortality_risk`.
- The population projection assumes the affected fraction of each municipality stays constant over time (only the municipality's total population changes) — it does not model migration within a municipality towards or away from the flood-prone area specifically.

## `App.py` + `pages/` — Interactive multi-page viewer (Streamlit)

A multi-page Streamlit app with a sidebar navigation menu — `App.py` is just a thin router (`st.set_page_config` + `st.navigation`); each hazard is its own page under `pages/`:

- **`pages/heat.py`** — the heat-mortality view: two side-by-side maps (2030 left, 2050 right) with **Escenario (SSP/RCP)** and **Variable** dropdowns (riesgo de mortalidad por calor / índice de calor diurno / índice de calor nocturno), plus the two summary tables (top 10 increments, top 10 cities) described below.
- **`pages/flood.py`** — a **Periodo de retorno** dropdown (10/100/500 years) driving two side-by-side maps of projected affected population (2030 left, 2050 right — the flood zones themselves don't change, only who lives in them, see the pipeline section above), each with its own top-10-municipalities table directly beneath it.
- **`pages/drought.py`**, **`pages/wildfire.py`** — placeholders (`st.info`) until those hazards are implemented.
- **`pages/combined.py`** — one map overlaying heat and flood risk as separate toggleable layers (Folium layer control), so both can be compared spatially. Drought/wildfire will be added here once implemented; no blended/composite score is computed — "combined" means overlaid layers, not a fabricated single number mixing risks that are on different scales and don't share a common unit.

The color scale (`vmin`/`vmax`) for the heat page is fixed per variable across both years and both scenarios (not recomputed per view), so color is visually comparable when switching selections — mixing scales across variables wouldn't make sense, since `heat_mortality_risk` is 0–1 while the Heat Index columns are in °C. Municipalities with a null value (see known limitations above) render gray instead of crashing the colormap.

The two heat-page tables: **top 10 municipalities by 2030→2050 increment** for the selected scenario/variable, and **top 10 Spanish cities by population** (fixed list — Madrid, Barcelona, València, Zaragoza, Sevilla, Málaga, Murcia, Palma, Alacant/Alicante, Bilbao, ranked by 2025 population — the ranking is stable enough not to need recomputing per year/scenario) showing the same variable's 2030/2050 values and increment, since a city might not show up in the "biggest increment" list even though it matters more in absolute terms. Both are joined by `ine_code`, not name: 17 municipality names repeat nationally (e.g. two different "Mieres"), so a name-only join would silently merge unrelated municipalities.

Run with `streamlit run App.py` (or `python -m streamlit run App.py` if the `streamlit` command isn't on your PATH).

### Performance

Loading and rendering a national choropleth of ~8,100 municipalities is the slow part of this app, not fetching data. Two things keep it fast, both in `common.py`:
- **Precomputed colors.** Coloring by calling `branca`'s colormap once per feature inside Folium's per-feature `style_function` callback is the single biggest cost (measured: ~3.5s vs ~0.04s for the same 8,132 municipalities). Instead, the hex color for every municipality is computed once, vectorized, as a DataFrame column *before* handing the GeoDataFrame to Folium — the callback then just looks up a precomputed string.
- **`st.cache_resource` on the built map.** Building a Folium map (styling + serializing ~8,100 polygons to embedded GeoJSON) is expensive regardless of styling approach; re-rendering it identically every time Streamlit reruns the script (which happens on *every* widget interaction, even unrelated ones) would waste that cost repeatedly. Caching the constructed map object per `(archivo, columna, vmin, vmax, ...)` means switching back to an already-seen combination is close to instant. Measured: ~17s cold, ~4s once cached (the residual ~4s is Streamlit's own script re-execution plus recomputing the tables, not map building).

Both the heat and flood app-facing geojsons are also pre-simplified to a 0.001°/~111m geometry tolerance (done once, in the processing scripts, not at app load time) — see the known limitation notes in the pipeline sections above for the ~90% size reduction this gets.

## Data

- `shared/boundaries/municipios_espana.*` — national municipal boundary shapefile (CNIG, "Líneas Límite Municipales"), not tracked in git (see [Getting the boundary data](#getting-the-boundary-data)). Shared by every hazard.
- `heat/input/summer_max_min_{escenario}.zip` / `sis_temp_raw_{escenario}/` / `temperaturas_{año}_{escenario}_eurocordex.nc` — raw and processed Copernicus EURO-CORDEX temperature download (one raw download per scenario, one processed file per year×scenario).
- `heat/input/humedad_{año}_{escenario}.zip` / `cordex_humedad_raw_{año}_{escenario}/` / `humedad_{año}_{escenario}_eurocordex.nc` — raw and processed CORDEX humidity download (one per year×scenario).
- `heat/input/madrid_buildings.gpkg` — Madrid building footprints (for future building-level cost/exposure analysis; not yet used by any script).
- `heat/output/municipios_heatwave_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the heat-mortality risk indicators attached (full and app-optimized versions), one pair per year×scenario combination.
- `flood/input/t10/`, `flood/input/t100/`, `flood/input/t500/` — raw SNCZI flood-risk shapefiles, not tracked in git (see [Getting the flood data](#getting-the-flood-data)).
- `flood/output/municipios_inundacion.geojson` / `_lite.geojson` — municipalities with flood risk indicators attached (full and app-optimized versions).
- `{heat,flood,drought,wildfire}/QGIS/` — QGIS project files for visualizing each hazard.

Large/generated data files, boundary shapefiles, and API credentials are excluded from version control (see `.gitignore`) — they're either downloaded by the scripts above or fetched manually as described below.

### Getting the boundary data

Download "Líneas Límite Municipales" (national municipal boundaries) from the [CNIG Download Center](https://centrodedescargas.cnig.es/CentroDescargas/limites-municipales-provinciales-autonomicos), free of charge. Extract the `recintos_municipales_inspire_peninbal_etrs89` shapefile (peninsula + Balearics) from the `SHP_ETRS89` folder and place its files in `shared/boundaries/`, renamed to `municipios_espana.*`. (The Canary Islands boundary set, in a different CRS, is handled separately — not yet wired into the pipeline.)

### Getting the flood data

Download the "riesgo de población" (risk to population) shapefiles for Peninsula + Baleares from MITECO, one per return period (these are click-through downloads, not stable direct-download URLs):
- [T=10 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t10.html) (~300MB)
- [T=100 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t100.html) (~390MB)
- [T=500 years](https://www.miteco.gob.es/en/cartografia-y-sig/ide/descargas/agua/riesgo-inundacion-fluvial-t500.html) (~370MB)

Extract each into `flood/input/t10/`, `flood/input/t100/`, `flood/input/t500/` respectively. Free to use with MITECO attribution.

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
- `pytest` (for `test_app.py`)

## Testing

`test_app.py` covers the whole app: smoke tests (every page under `pages/` renders without exceptions, navigated to via `AppTest.switch_page()`), detailed checks on the heat page across every scenario×variable combination, and data sanity checks on both hazards' geojsons (expected columns, row counts, value ranges, no more nulls than the documented known-limitations count, majority-positive 2030→2050 heat deltas, flood risk increasing with return period). Run with:

```
python -m pytest test_app.py -v
```

Each unique scenario/variable combination spins up a real `streamlit.testing.v1.AppTest` run (~15–20s), so the full suite takes a few minutes; results are cached per combination so multiple assertions against the same combination don't re-run the app.

## Next steps

- Add drought risk from the SPEI Global Drought Monitor, using the same raster-clip-per-municipality approach as the heat script.
- Add wildfire risk from EFFIS historical burnt-area data.
- Merge all hazard indicators into a single national GeoPackage plus a styled QGIS project.
- Translate hazard indicators into estimated economic costs per municipality.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

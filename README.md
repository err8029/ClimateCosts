# ClimateCosts

Modeling the impact of climate change — heat, flooding, wildfire, and drought — on every municipality in Spain, using official climate and hazard data, for visualization in QGIS.

## Status

All four hazards are now implemented: nationwide heat-mortality risk (Heat Index from temperature + humidity, weighted by population, across 2 years × 2 emissions scenarios), flood risk (MITECO population exposure, current + projected, plus a separate Copernicus-derived projected river discharge intensity indicator under RCP4.5/8.5), drought risk (meteorological drought duration + magnitude, current + projected), and wildfire risk (fire danger index + high-danger days weighted by population, same structure as heat) — plus a blended `combined_risk` score (40/30/15/15 weight by hazard, reweighted when a component is missing rather than going null) and a `financial_impact_eur`/`financial_impact_eur_per_capita` proxy (GDP-per-capita-based economic exposure, same hazard weighting — see the Pipeline section), all behind a login-gated multi-page Streamlit app (`App.py` + `pages/`) with a sidebar-navigable page per hazard, a combined-risk page (+ raw overlay view), and a financial-impact page. See [Next steps](#next-steps) for what's left.

## Approach

Each hazard is modeled independently and stored as its own indicator column(s) on the national municipal boundary layer, rather than blended into a single score — so each can be toggled and styled separately in QGIS. Where an official hazard dataset exists (flood zones, fire history, drought indices), that's used in preference to deriving risk purely from raw climate projections.

| Hazard | Source |
|---|---|
| Heat-mortality | Copernicus C3S EURO-CORDEX-derived temperature statistics (max + min) + raw CORDEX humidity (Heat Index) + INE municipal population, projected to 2030/2050 via provincial growth rates |
| Flood | MITECO SNCZI "riesgo de población" flood-risk maps (T=10/100/500yr) for population exposure + Copernicus/EEA `sis-ecde-climate-indicators` (`flood_recurrence`) for projected river discharge intensity (1-in-2/5/10/50yr, RCP4.5/8.5) |
| Drought | Copernicus/EEA `sis-ecde-climate-indicators` — meteorological drought duration + magnitude (SPI-3), derived from bias-corrected CORDEX, projected to 2030/2050 |
| Wildfire | Copernicus/EEA `sis-ecde-climate-indicators` — Canadian Fire Weather Index + days/year of high fire danger, weighted by population, projected to 2030/2050 (same structure as heat-mortality) |

## Project structure

Each hazard is a self-contained folder with its own scripts, raw downloads, generated outputs, and QGIS project:

```
ClimateCosts/
├── App.py                    # Streamlit entry point: login gate + st.navigation router
├── auth.py                    # Login form + credential verification (see Authentication)
├── generar_credenciales.py    # Interactive helper to (re)generate login credentials
├── common.py                  # Shared map-building/caching helpers used by pages/*.py
├── regenerate_data.py          # Runs every pipeline script below in order, with progress feedback
├── requirements.txt             # pip-installable dependency list
├── .streamlit/
│   ├── secrets.toml             # Login credentials (hash only) - not tracked in git
│   └── secrets.toml.example     # Template for secrets.toml
├── pages/
│   ├── heat.py                 # Heat-mortality risk page
│   ├── flood.py                 # Flood risk page
│   ├── drought.py                # Drought risk page
│   ├── wildfire.py                # Wildfire risk page
│   ├── combined_risk.py            # Blended combined_risk page + multi-hazard overlay
│   └── financial_impact.py          # financial_impact_eur page (total + per-capita)
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
│   ├── 4_extract_discharge_data.py  # Downloads sis-ecde-climate-indicators (flood_recurrence)
│   ├── 5_river_discharge_risk.py    # Computes river_discharge_{2y,5y,10y,50y} per municipality
│   ├── input/                  # Raw SNCZI shapefiles (t10/t100/t500) + discharge_raw_{periodo}_{escenario}/
│   ├── output/                 # municipios_inundacion(...) + municipios_river_discharge_{epoca}_{escenario}(...)
│   └── QGIS/
├── drought/
│   ├── 1_extract_data.py       # Downloads sis-ecde-climate-indicators (SPI-3 duration + magnitude)
│   ├── 2_drought_risk.py       # Computes drought_duration_months / drought_magnitude per municipality
│   ├── input/                  # Raw CDS downloads (drought_raw_{escenario}/)
│   ├── output/                 # municipios_drought_risk_{año}_{escenario}(.geojson|_lite.geojson)
│   └── QGIS/
├── wildfire/
│   ├── 1_extract_data.py       # Downloads sis-ecde-climate-indicators (fire_weather_index + days_with_high_fire_danger)
│   ├── 2_wildfire_risk.py      # Computes wildfire_risk per municipality (same structure as heat)
│   ├── input/                  # Raw CDS downloads (wildfire_raw_{escenario}/)
│   ├── output/                 # municipios_wildfire_risk_{año}_{escenario}(.geojson|_lite.geojson)
│   └── QGIS/
└── combined/
    ├── 1_combined_risk.py      # Blends all 4 hazards (40/30/15/15) into combined_risk
    ├── 2_financial_impact.py   # Translates combined_risk into euro proxies (total + per-capita)
    └── output/                 # municipios_combined_risk_{...} + municipios_financial_impact_{...}
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

### 4. `flood/4_extract_discharge_data.py` + `flood/5_river_discharge_risk.py` — Projected river discharge intensity

MITECO's SNCZI data (above) has no climate-scenario dimension at all — it's a fixed present-day hazard map. To get an actual RCP-scenario-driven flood signal, this uses the same `sis-ecde-climate-indicators` dataset as drought, this time its **`flood_recurrence`** variable: river discharge (m³/s) expected for a given return period, from two hydrological models (E-HYPE, VIC-WUR) forced by bias-corrected CORDEX, under RCP4.5/RCP8.5.

This is a **genuinely different indicator from the MITECO data above, not a replacement for it** — river discharge intensity tells you how much a river's flood-generating flow is projected to change, not how many people live in a flood-prone area. The two are shown as separate sections on `pages/flood.py` rather than merged into one number, same reasoning as keeping every hazard as its own column instead of a blended score. The return periods don't line up either: Copernicus offers 1-in-2/5/10/50-year, MITECO offers T=10/100/500-year — different studies, not interchangeable.

`4_extract_discharge_data.py` downloads, per scenario × return period (8 combinations), one small NetCDF that already contains **3 fixed 30-year climatological windows** (~2011–2040, ~2041–2070, ~2071–2100) rather than a yearly time series — Copernicus did the climatological averaging already, unlike the drought indicators. The GCM/RCM/ensemble/hydrological-model combination (`hadgem2_es`/`rca4`/`r1i1p1`/`combined_e_hype_and_vic_wur`) was again found via the `constraints` endpoint.

`5_river_discharge_risk.py` clips each municipality against the **first two** of those three windows (labeled by their real period, e.g. `2011_2040`, `2041_2070` — not relabeled to "2030"/"2050", since a 30-year window centered elsewhere would be misleading under those names). Unlike every other raster-clip in this project, it takes the **maximum** value within the municipality, not the mean: discharge is only meaningful on grid cells that sit on a watercourse (~36% of Spain's grid cells are NaN — no channel there), so averaging in the non-river cells would dilute the signal toward zero everywhere. A municipality with no significant watercourse inside it, or nearby via the nearest-point fallback, is left **null**, not zero — a missing channel isn't the same claim as "zero flood risk".

Output: `flood/output/municipios_river_discharge_{epoca}_{escenario}.geojson` / `_lite.geojson`, columns `river_discharge_2y`/`_5y`/`_10y`/`_50y`.

**Known limitations**:
- Only ~64% of Spain's grid cells have a value at all (the rest have no significant modeled watercourse) — expect many null municipalities, concentrated in areas far from rivers.
- The 3 available windows are fixed by Copernicus, not chosen by this project; using the first two as a "near/mid-century" comparison pair means skipping the ~2071–2100 window entirely to keep the same two-map layout used everywhere else in the app.
- `flood_recurrence` measures the same hazard-defining discharge across the whole country with one model chain — it hasn't been calibrated against the specific rivers behind MITECO's Spanish flood maps, so the two indicators are not on a comparable scale or methodology, only complementary in spirit.

### 5. `drought/1_extract_data.py` + `drought/2_drought_risk.py` — Drought risk by municipality

The official CSIC SPEIbase (SPEI-6/SPEI-12) is historical-only — there's no future/projected version of it, and its download portal (`digital.csic.es`) blocks scripted access. Instead this uses Copernicus's `sis-ecde-climate-indicators` dataset, which provides **duration** (months/year in drought) and **magnitude** (severity) of meteorological drought based on **SPI-3** (3-month Standardised Precipitation Index — precipitation deficit only, *not* SPEI, which also factors in evapotranspiration), derived from bias-corrected CORDEX and covering 1970–2098 under RCP4.5/RCP8.5. This is a genuine tradeoff: an index at a different timescale than originally wanted, in exchange for actual official 2030/2050 projections instead of a from-scratch homemade proxy.

`1_extract_data.py` downloads, per scenario, both variables as one yearly gridded (~0.25°/~25km) NetCDF time series spanning the full period — one download per scenario (2 total), no need to loop by year. The specific GCM/RCM/ensemble-member combination (`hadgem2_es`/`rca4`/`r1i1p1` — same model family as the heat humidity data) isn't freely choosable: only certain pre-computed combinations exist, discovered via the CDS API's `constraints` endpoint (not documented on the dataset's web page).

`2_drought_risk.py` then, per year×scenario: takes a **20-year climatological window average** centered on the target year (2021–2040 for 2030, 2041–2060 for 2050) rather than a single year's value — single-year values are noisy (e.g. Spain-wide mean duration jumped 2.9→1.7→3.2→5.3 months across just 4 individual years in a row in the raw data), the same lesson learned the hard way with heat's per-year normalization bug. Clips the windowed grid to each municipality the same way as the heat script (nearest-point fallback for municipalities smaller than a grid cell — used more often here than for heat, since this grid is ~2× coarser).

Output: `drought/output/municipios_drought_risk_{año}_{escenario}.geojson` (full) and `_lite.geojson` (`drought_duration_months`, `drought_magnitude`, simplified geometry). No combined/blended drought score is computed — same reasoning as flood, two separate official indicators rather than an invented composite.

**Known limitations**:
- SPI-3 measures precipitation deficit only; it doesn't account for evapotranspiration (temperature-driven water demand), so it will understate drought severity in a warming climate relative to a true SPEI.
- ~0.25° (~25km) grid resolution is much coarser than heat's ~11km grid, so many neighboring small municipalities share the same underlying grid value — expect visibly "blocky" patterns on the map rather than fine per-municipality gradients.
- The 20-year window is a modeling choice (not an official CDS aggregation), made to reduce single-year noise; a different window length would shift the exact numbers somewhat, though not the overall trend.

### 6. `wildfire/1_extract_data.py` + `wildfire/2_wildfire_risk.py` — Wildfire risk by municipality

Same structure as heat-mortality risk, deliberately: two raw climate danger variables + projected population, combined in equal thirds into one relative risk proxy, across the same 2030/2050 × RCP4.5/RCP8.5 matrix. The climate variables come from `sis-ecde-climate-indicators` again — `fire_weather_index` (the Canadian Forest Fire Weather Index, a standard fire-danger index) and `days_with_high_fire_danger` (days/year above a high-danger threshold) — this time needing only a GCM (no RCM/ensemble-member/hydrological-model choice, unlike drought/flood-discharge).

`1_extract_data.py` downloads both variables per scenario as one yearly time series (same pattern as drought — no fixed climatological windows like flood's `flood_recurrence`, so the risk script does its own 20-year windowing). `2_wildfire_risk.py` reuses heat's population-projection code verbatim (same INE tables, same province growth-factor extrapolation) and heat's exact fixed-range-normalization formula: `wildfire_risk = (fire_weather_index_norm + high_fire_danger_days_norm + poblacion_norm) / 3`, normalized once across all 4 year×scenario combinations so the score tracks real change over time rather than each year's relative ranking (see heat's Known limitations for why that distinction matters).

Per-municipality extraction found a bug worth noting: unlike heat/drought's grids, this one has NaN cells scattered *within* land area (not just over the ocean), so `rio.clip()` can succeed while still returning all-NaN — no exception is raised, so a naive try/except never falls back to the nearest-point lookup. Fixed by explicitly checking `np.isfinite()` after every clip (and after the nearest-point fallback too) instead of trusting the exception path.

Output: `wildfire/output/municipios_wildfire_risk_{año}_{escenario}.geojson` / `_lite.geojson` (`wildfire_risk`, `fire_weather_index`, `high_fire_danger_days`).

**Known limitations**:
- A much wider coastal band than heat's is masked out in this dataset (~535 municipalities with no `fire_weather_index` value, vs. heat's ~33) — including some large coastal cities (València, Alacant/Alicante), which is why `pages/wildfire.py`'s "top cities" table can show fewer than 10 rows.
- Same population-projection caveats as heat (2050 figures are an extrapolation beyond INE's published 2026–2041 range).
- No wind-direction or fuel-load data is incorporated — this is a *weather-driven fire danger* proxy (matching what the underlying Canadian FWI actually measures), not a full fire-spread or vegetation-fuel model.

### 7. `combined/1_combined_risk.py` — Combined risk (weighted by hazard)

Joins the outputs of all 4 hazard pipelines above and blends them into one `combined_risk` score per municipality, per year×scenario. Each hazard contributes exactly one representative variable, weighted **40% heat / 30% flood / 15% drought / 15% wildfire** (not equal weights — see the rationale below, shared with `financial_impact_eur`):

| Hazard | Variable used | Why |
|---|---|---|
| Heat | `heat_mortality_risk` | Already a 0–1 composite by construction — used as-is. |
| Flood | `flood_risk_t100_poblacion_afectada_{año}` (projected affected population, T=100yr), normalized | Not the `flood_risk_t100` fraction — that's fixed regardless of year (MITECO zones don't change), so using it would make flood's contribution identical for 2030 and 2050. The projected affected-population count *does* vary by year, so the combined score actually reflects demographic change in flood-prone areas the same way heat's population term does. |
| Drought | mean of normalized `drought_duration_months` and normalized `drought_magnitude` | Neither is naturally 0–1, so each gets its own fixed-range normalization (same methodology as every other hazard in this project) before averaging. |
| Wildfire | `wildfire_risk` | Already a 0–1 composite by construction — used as-is. |

The normalization ranges for flood and drought are computed fresh, here, across the 4 year×scenario combinations being generated — **not** reused from `pages/flood.py`/`pages/drought.py`'s own display logic. This was an explicit choice: it keeps all 4 components in one coherent, self-contained normalization space for the combined score specifically, rather than silently inheriting whatever normalization decisions happen to already be baked into each hazard's own page.

It's a **weighted sum, not a product**: a component being 0 (or missing) doesn't zero out the rest, it just contributes nothing to its own slice. When a municipality is missing one or more components (in practice, almost always wildfire's coastal data gap — see wildfire's Known limitations), the remaining weights are **rescaled to sum to 1 among just the available components**, rather than leaving `combined_risk` null. A municipality is only left without a score if *all 4* components are missing, which doesn't happen in practice (every municipality has at least drought data, since that hazard has no coverage gaps at all).

Output: `combined/output/municipios_combined_risk_{año}_{escenario}.geojson` / `_lite.geojson` (`combined_risk`, `calor_norm`, `inundacion_norm`, `sequia_norm`, `incendio_norm`).

**Known limitations**:
- Inherits every individual hazard's own known limitations (population-projection extrapolation, wildfire's coastal data gap, SPI-3 vs. SPEI, etc.) — see each hazard's own section above.
- The 40/30/15/15 weighting is a defensible *relative ordering* grounded in published research (see `financial_impact_eur` below for the sources), not a precision-fitted regression — it does not claim to know the exact economic cost per unit of physical risk for each hazard, only their rough relative order of magnitude.
- When components are missing and weights get rescaled, a municipality's score reflects *only* the hazards with data for it — comparing such a municipality directly against one with all 4 components should be done with that caveat in mind.

### 8. `combined/2_financial_impact.py` — Financial impact proxy (€)

Translates `combined_risk` into two euro figures per municipality — **total** exposure and **per-capita** exposure — because they answer different questions and rank municipalities very differently:

```
valor_economico_eur          = población proyectada(año) × PIB per cápita provincial
financial_impact_eur         = valor_economico_eur × combined_risk
financial_impact_eur_per_capita = PIB per cápita provincial × combined_risk   (población se cancela algebraicamente)
```

`financial_impact_eur` (total) necessarily grows with population, so it's dominated by the biggest cities regardless of how physically at-risk they actually are (Madrid topped every ranking under the first version of this metric largely because of its sheer economic scale, not because it's uniquely vulnerable). `financial_impact_eur_per_capita` **doesn't depend on municipality size at all** — the population term cancels out algebraically, leaving just `PIB per cápita × combined_risk` — so it re-ranks toward municipalities where climate risk threatens the largest *share* of local economic life, independent of scale. Both are shown side by side on `pages/financial_impact.py` (a **Variable** dropdown switches between them) rather than picking one, since "where's the most total € at risk nationally" (useful for infrastructure/budget prioritization) and "where is risk most concentrated relative to the local economy" are both legitimate, different questions.

Two deliberate departures from `combined_risk`'s own methodology, both requested explicitly rather than assumed:

1. **Exposure base is economic value, not headcount.** `PIB per cápita` comes from INE's Contabilidad Regional de España (table `76926`, "PRODUCTO INTERIOR BRUTO A PRECIOS DE MERCADO" by province) divided by current provincial population — INE doesn't publish municipal-level GDP, so this uses the same province→municipality extrapolation already used for population growth elsewhere in this project (every municipality in a province is assumed to share its province's per-capita GDP — this is why Madrid-province commuter towns like Móstoles, Getafe, or Alcobendas cluster near the top of the per-capita ranking too, not just Madrid city itself). GDP per capita itself is **held constant in real terms** — only population is projected to 2030/2050 — because projecting GDP growth on top of an already-approximate population projection would stack two speculative assumptions instead of one.
2. **The 4 hazards are weighted 40/30/15/15 (heat/flood/drought/wildfire), not equally**, and — since `combined_risk` itself now uses these same weights — this is really one shared weighting scheme rather than two. The relative weights are grounded in the EU Joint Research Centre's PESETA IV study (the reference EU assessment of climate damage costs by hazard) and aggregate loss reporting: heat dominates in welfare-loss terms in Southern Europe (mortality + lost labor productivity) and gets the largest weight; river flooding is the second-largest cost but highly event-concentrated (e.g. the October 2024 Valencia DANA alone caused >€17bn, over 20% of that province's annual GDP, in a single event); drought and wildfire are typically a smaller order of magnitude in an average year, though both can spike severely in a bad regional year (drought losses reached 15% of regional GDP in the worst-hit Mediterranean regions per JRC; Spain+Portugal accounted for 43% of all EU wildfire burnt area in 2025).

Output: `combined/output/municipios_financial_impact_{año}_{escenario}.geojson` / `_lite.geojson` (`financial_impact_eur`, `financial_impact_eur_per_capita`, `valor_economico_eur`, `pib_per_capita`, `combined_risk` passed through for the page's tables — see below).

**Known limitations — read before treating any number here as a real damage estimate**:
- This is an order-of-magnitude proxy, not a calibrated damage model. The 40/30/15/15 weights are a defensible *relative ordering* grounded in real published research, not a precision-fitted regression — the underlying sources mix different time horizons (present-day, 2029, 2050, 2100), different warming/scenario levels, and fundamentally different loss concepts (heat figures are largely monetized-mortality/welfare loss; flood/drought/wildfire figures are more often direct asset/output damage) that aren't strictly comparable to each other.
- GDP per capita held constant in real terms ignores real economic growth, structural change, and inflation between now and 2030/2050 — a genuine simplification, not an estimate of future GDP.
- The per-capita figure is identical for every municipality in the same province with the same `combined_risk` — it inherits the province-level GDP extrapolation's inability to distinguish a provincial capital from a small town in the same province.
- Only null for the ~88 mancomunidades without an INE population figure (same gap as `heat_mortality_risk`) — `combined_risk`'s own reweighting means the wildfire coastal gap no longer propagates here.

## `App.py` + `pages/` — Interactive multi-page viewer (Streamlit)

A multi-page Streamlit app with a sidebar navigation menu — `App.py` is just a thin router (`st.set_page_config` + `st.navigation`); each hazard is its own page under `pages/`:

- **`pages/heat.py`** — the heat-mortality view: two side-by-side maps (2030 left, 2050 right) with **Escenario (SSP/RCP)** and **Variable** dropdowns (riesgo de mortalidad por calor / índice de calor diurno / índice de calor nocturno), plus the two summary tables (top 10 increments, top 10 cities) described below.
- **`pages/flood.py`** — two stacked sections, since flood risk comes from two genuinely different sources (see the pipeline sections above). First, MITECO population exposure: a **Periodo de retorno** dropdown (10/100/500 years) driving two side-by-side maps of projected affected population (2030 left, 2050 right — the flood zones themselves don't change, only who lives in them), plus the same two summary tables below (top 10 increments, top 10 cities). Below that, projected river discharge intensity: **Escenario (RCP)** and **Periodo de retorno** dropdowns (2/5/10/50 years) driving two side-by-side maps of projected discharge for the two available climatological windows (`2011_2040`/`2041_2070`), plus the same two summary tables.
- **`pages/drought.py`** — same layout again: **Escenario (RCP)** and **Variable** dropdowns (duración de la sequía / magnitud de la sequía), two side-by-side maps (2030/2050), plus the same two summary tables below.
- **`pages/wildfire.py`** — same layout as `pages/heat.py`: **Escenario (RCP)** and **Variable** dropdowns (riesgo de incendio forestal / índice de peligro (Canadian FWI) / días de peligro alto), two side-by-side maps (2030/2050), plus the same two summary tables below.
- **`pages/combined_risk.py`** — two stacked sections. First, the blended `combined_risk` score (see the pipeline section above): an **Escenario (RCP)** dropdown driving two side-by-side maps (2030/2050), plus the same two summary tables (top 10 increments, top 10 cities) as every other hazard page. Below that, the raw overlay view: heat, flood, drought, and wildfire risk as separate toggleable layers (Folium layer control) on one map, so the 4 raw layers can be compared spatially side by side — a different, complementary view from the blended score above, not a duplicate of it.
- **`pages/financial_impact.py`** — its own page (separate from the risk score, since it answers a different question). **Escenario (RCP)** and **Variable** dropdowns — the Variable choice switches between "Impacto total (€)" (colored on a **log scale**, since a few large cities are orders of magnitude above everywhere else — a linear scale would leave almost the entire map one flat color) and "Impacto per cápita (€/habitante)" (linear scale — without total's population-driven long tail, linear already spreads the contrast well). Same two-map layout as every other page; the tables add two things beyond the usual 2030/2050/increment columns: the underlying **GDP forecast** (total PIB or PIB per cápita, matching whichever Variable is selected) for context next to the impact figure, and an **"Incremento riesgo (pp)"** column — percentage points of `combined_risk` itself (2050 minus 2030), which isolates how much the underlying *risk share* grew from how much the € figures grew simply because the GDP base itself grew.

The color scale (`vmin`/`vmax`) for the heat page is fixed per variable across both years and both scenarios (not recomputed per view), so color is visually comparable when switching selections — mixing scales across variables wouldn't make sense, since `heat_mortality_risk` is 0–1 while the Heat Index columns are in °C. Municipalities with a null value (see known limitations above) render gray instead of crashing the colormap.

The two heat-page tables: **top 10 municipalities by 2030→2050 increment** for the selected scenario/variable, and **top 10 Spanish cities by population** (fixed list — Madrid, Barcelona, València, Zaragoza, Sevilla, Málaga, Murcia, Palma, Alacant/Alicante, Bilbao, ranked by 2025 population — the ranking is stable enough not to need recomputing per year/scenario) showing the same variable's 2030/2050 values and increment, since a city might not show up in the "biggest increment" list even though it matters more in absolute terms. Both are joined by `ine_code`, not name: 17 municipality names repeat nationally (e.g. two different "Mieres"), so a name-only join would silently merge unrelated municipalities.

Run with `streamlit run App.py` (or `python -m streamlit run App.py` if the `streamlit` command isn't on your PATH).

### Performance

Loading and rendering a national choropleth of ~8,100 municipalities is the slow part of this app, not fetching data. Two things keep it fast, both in `common.py`:
- **Precomputed colors.** Coloring by calling `branca`'s colormap once per feature inside Folium's per-feature `style_function` callback is the single biggest cost (measured: ~3.5s vs ~0.04s for the same 8,132 municipalities). Instead, the hex color for every municipality is computed once, vectorized, as a DataFrame column *before* handing the GeoDataFrame to Folium — the callback then just looks up a precomputed string.
- **`st.cache_resource` on the built map.** Building a Folium map (styling + serializing ~8,100 polygons to embedded GeoJSON) is expensive regardless of styling approach; re-rendering it identically every time Streamlit reruns the script (which happens on *every* widget interaction, even unrelated ones) would waste that cost repeatedly. Caching the constructed map object per `(archivo, columna, vmin, vmax, ...)` means switching back to an already-seen combination is close to instant. Measured: ~17s cold, ~4s once cached (the residual ~4s is Streamlit's own script re-execution plus recomputing the tables, not map building).

Every hazard's app-facing geojsons are also pre-simplified to a 0.001°/~111m geometry tolerance (done once, in the processing scripts, not at app load time) — see the known limitation notes in the pipeline sections above for the ~90% size reduction this gets.

## Authentication

`App.py` shows a login form (`auth.py`) before any page content, gated by a single username/password pair. The password is never stored or compared in plain text: only a salted **PBKDF2-SHA256** hash (200,000 iterations) lives in `.streamlit/secrets.toml`, which is **not tracked in git** (see `.gitignore`) — only `.streamlit/secrets.toml.example`, a template with no real values, is committed. Comparison uses `hmac.compare_digest` (constant-time) for both the username and the password hash, to avoid leaking timing information about a partial match.

To set up or change the login credentials:

```
python generar_credenciales.py
```

This prompts for a username and password (the password isn't echoed to the terminal), generates a fresh random salt, and prints a `[auth]` block to paste into `.streamlit/secrets.toml`.

**Known limitation**: this is a single shared login for a low-stakes internal tool, not a hardened multi-user auth system — there's no rate-limiting on login attempts, and a short numeric PIN (as opposed to a longer password) is trivially brute-forceable *offline* if the hash and salt themselves were ever exposed (e.g. `secrets.toml` accidentally committed). The hashing protects against a leaked file being immediately readable as a password, not against a determined offline attack on a weak PIN — use a longer, less guessable password if that matters for your deployment.

## Data

- `shared/boundaries/municipios_espana.*` — national municipal boundary shapefile (CNIG, "Líneas Límite Municipales"), not tracked in git (see [Getting the boundary data](#getting-the-boundary-data)). Shared by every hazard.
- `heat/input/summer_max_min_{escenario}.zip` / `sis_temp_raw_{escenario}/` / `temperaturas_{año}_{escenario}_eurocordex.nc` — raw and processed Copernicus EURO-CORDEX temperature download (one raw download per scenario, one processed file per year×scenario).
- `heat/input/humedad_{año}_{escenario}.zip` / `cordex_humedad_raw_{año}_{escenario}/` / `humedad_{año}_{escenario}_eurocordex.nc` — raw and processed CORDEX humidity download (one per year×scenario).
- `heat/input/madrid_buildings.gpkg` — Madrid building footprints (for future building-level cost/exposure analysis; not yet used by any script).
- `heat/output/municipios_heatwave_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the heat-mortality risk indicators attached (full and app-optimized versions), one pair per year×scenario combination.
- `flood/input/t10/`, `flood/input/t100/`, `flood/input/t500/` — raw SNCZI flood-risk shapefiles, not tracked in git (see [Getting the flood data](#getting-the-flood-data)).
- `flood/output/municipios_inundacion.geojson` / `_lite.geojson` — municipalities with flood risk indicators attached (full and app-optimized versions).
- `flood/input/discharge_{periodo}_{escenario}.zip` / `discharge_raw_{periodo}_{escenario}/` — raw Copernicus `sis-ecde-climate-indicators` (`flood_recurrence`) download, one per return-period×scenario combination (8 total).
- `flood/output/municipios_river_discharge_{epoca}_{escenario}.geojson` / `_lite.geojson` — municipalities with projected river discharge indicators attached, one pair per climatological-window×scenario combination.
- `drought/input/drought_{escenario}.zip` / `drought_raw_{escenario}/` — raw Copernicus `sis-ecde-climate-indicators` download (one per scenario, covering the full 1970-2098 time series).
- `drought/output/municipios_drought_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with drought duration/magnitude indicators attached, one pair per year×scenario combination.
- `wildfire/input/wildfire_{escenario}.zip` / `wildfire_raw_{escenario}/` — raw Copernicus `sis-ecde-climate-indicators` download (one per scenario, covering the full 1985-2083 time series).
- `wildfire/output/municipios_wildfire_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the wildfire risk indicators attached, one pair per year×scenario combination.
- `combined/output/municipios_combined_risk_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the blended `combined_risk` score attached, one pair per year×scenario combination.
- `combined/output/municipios_financial_impact_{año}_{escenario}.geojson` / `_lite.geojson` — municipalities with the `financial_impact_eur` and `financial_impact_eur_per_capita` proxies attached, one pair per year×scenario combination.
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

### Regenerating the data

Once the boundary data, flood shapefiles, and a valid `.cdsapirc` are in place (above), a single command runs every extraction + risk script in order and reports progress as it goes:

```
python regenerate_data.py
```

It checks the manual-download prerequisites up front (fails fast with a clear message if any are missing, rather than partway through the pipeline), then runs each of the 10 pipeline scripts as a subprocess, printing `[step/10] (X%) <description>` before each one and how long it took after. Every individual script already skips re-downloading data it already has (see each script's own `if os.path.exists(...)` checks), so re-running `regenerate_data.py` after fixing a failed step doesn't repeat completed work. If a step fails, it stops immediately and reports which one and why, rather than continuing with stale/missing downstream data.

## Requirements

Install with `pip install -r requirements.txt`, or manually:

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

`test_app.py` covers the whole app: login tests (form appears when unauthenticated, wrong credentials rejected, the PBKDF2 hashing/comparison mechanism itself verified with synthetic test credentials — never the real production password, which never appears in the test suite), smoke tests (every page under `pages/` renders without exceptions, navigated to via `AppTest.switch_page()`), detailed checks on the heat/drought/wildfire/combined-risk/financial-impact pages across every scenario×variable combination and on flood's river-discharge section across every scenario×return-period combination, and data sanity checks on every hazard's geojsons (expected columns, row counts, value ranges, no more nulls than the documented known-limitations count, majority-positive 2030→2050 deltas, flood/discharge risk increasing with return period, `combined_risk` verified to equal its exact weighted-sum formula, `financial_impact_eur` verified non-negative and never exceeding its own `valor_economico_eur` base). Content tests bypass the login form by pre-seeding `AppTest`'s session state (`autenticado=True`) rather than depending on real or fake credentials. Run with:

```
python -m pytest test_app.py -v
```

Each unique scenario/variable combination spins up a real `streamlit.testing.v1.AppTest` run (~15–20s), so the full suite takes a few minutes; results are cached per combination so multiple assertions against the same combination don't re-run the app.

## Next steps

- Add wildfire spread/burnt-area history (e.g. EFFIS) alongside the current weather-driven fire-danger proxy, for a more complete picture than danger-index-only.
- Merge all hazard indicators into a single national GeoPackage plus a styled QGIS project.
- Refine `financial_impact_eur`'s hazard cost coefficients (currently 40/30/15/15, grounded in JRC PESETA IV but not precisely calibrated to Spain — see Known limitations) as more Spain-specific, same-horizon loss data becomes available.
- Incorporate building-level exposure data (`madrid_buildings.gpkg`).

## License

GPL-3.0 — see [LICENSE](LICENSE).

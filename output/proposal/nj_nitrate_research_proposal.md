# New Jersey Nitrate Hotspot Research Proposal

## Project Title

**Identifying and Explaining Nitrate Hotspots in New Jersey Watersheds Using Water Quality Portal Data, Land Use Patterns, and NJPDES Facility Density**

---

## 1. Abstract

This project investigates nitrate and nitrate + nitrite pollution patterns in and around New Jersey using Water Quality Portal monitoring records from 2000 to 2026. The study identifies nitrate hotspot stations, compares seasonal and long-term nitrate trends, joins station results to watershed boundaries, and evaluates whether hotspot patterns are associated with land use composition and NJPDES regulated facility density.

The analysis finds that nitrate hotspots are not randomly distributed across watersheds. Several highly developed watersheds, especially Lower Passaic and Saddle and Hackensack/Hudson/Pascack, show elevated nitrate hotspot rates and mean nitrate concentrations. Watershed-level correlation analysis suggests that developed land percentage is more strongly associated with nitrate hotspot patterns than agriculture percentage in this dataset. NJPDES facility density also shows associations with nitrate patterns, but multivariable regression indicates that facility density may partly act as a proxy for developed land rather than a clearly independent predictor of hotspot rate or mean nitrate.

Because the study uses watershed-level observational data, the findings should be interpreted as exploratory associations rather than causal evidence. The latest pipeline now joins EPA ICIS-NPDES DMR flow/load summaries by normalized permit ID, reports DMR match coverage by permit group and facility type, adds watershed-centroid rainfall, simple watershed-shape metrics, an upstream facility-density proxy, NHD flowline context, and snapped outfall proxy points. Exact regulatory outfall coordinates are still not present in the current DMR/NJPDES files, so the website labels the snapped points as proxies rather than observed outfall coordinates.

---

## 2. Background and Rationale

Nitrate is an important water-quality indicator because elevated nitrate concentrations can be linked to fertilizer runoff, wastewater discharge, septic systems, urban stormwater, groundwater movement, and other human or environmental factors. High nitrate levels can affect aquatic ecosystems and may indicate broader nutrient pollution issues.

New Jersey is a useful study area because it contains dense urban regions, suburban development, agricultural areas, wetlands, industrial corridors, and many regulated discharge facilities. This makes it possible to compare different watershed conditions and examine whether nitrate hotspots align more strongly with developed land, agricultural land, or facility density.

---

## 3. Research Questions

1. Where are nitrate hotspot stations located in and around New Jersey?
2. Are nitrate hotspots randomly distributed, or do they cluster in specific watersheds?
3. Are nitrate hotspot watersheds more associated with developed land or agricultural land?
4. Are NJPDES facility density and facility type associated with nitrate hotspot patterns?
5. After controlling for developed land, does facility density still add explanatory value?
6. What limitations prevent this analysis from proving causation?

---

## 4. Data Sources

### Water Quality Data

The main water-quality dataset comes from the Water Quality Portal and includes nitrate and nitrate + nitrite monitoring records from 2000 to 2026.

### Watershed Data

New Jersey watershed management area boundaries were used to summarize nitrate hotspot patterns by watershed.

### Land Use Data

New Jersey 2020 Land Use / Land Cover polygons were used to calculate watershed-level land use composition, including developed land, agriculture, forest, wetlands, water, and barren land.

### NJPDES Facility Data

NJPDES regulated facility locations were joined to watersheds. Facilities were grouped into categories such as industrial stormwater, septic/groundwater, groundwater discharge, stormwater/surface discharge, residuals/recycling, construction/permit, and mining/quarrying.

---

## 5. Methods

### 5.1 Data Cleaning

Raw Water Quality Portal records were filtered to water samples, cleaned for numeric nitrate values, and standardized into comparable units. Missing values, quality-control samples, negative values, and records without valid locations were removed.

### 5.2 Nitrate Extraction

Both nitrate and nitrate + nitrite records were retained because both are relevant to nitrogen pollution analysis. The final nitrate dataset included standardized numeric concentration values and station coordinates.

### 5.3 Station-Level Hotspot Detection

Each station was summarized using mean nitrate, p90 nitrate, maximum nitrate, observation count, and confidence category. Hotspots were defined as stations in the top 10% by mean nitrate or top 10% by p90 nitrate.

Key station-level summary:

- Total stations: 3658
- Hotspot stations: 411
- High-confidence stations: 76

### 5.4 Seasonal and Long-Term Trend Analysis

Nitrate values were grouped by season, month, and year to examine temporal patterns. Moving averages were used to reduce noise in long-term trend visualization.

### 5.5 Watershed Spatial Join

Station summary data were spatially joined to New Jersey watershed boundaries. Each watershed was summarized by station count, hotspot count, hotspot rate, mean nitrate, p90 nitrate, and monitoring confidence.

### 5.6 Land Use Overlay

Land use polygons were overlaid with watershed boundaries. Each watershed received percentages for developed, agriculture, forest, wetlands, water, and barren land. These percentages were compared with nitrate hotspot metrics.

### 5.7 NJPDES Facility Join

NJPDES facility locations were spatially joined to watersheds. Facility counts and facility densities per 100 km2 were calculated overall and by facility type.

### 5.8 Correlation and Regression Analysis

The project used Pearson and Spearman correlations to compare land use and facility variables with nitrate metrics. A multivariable regression step then tested whether facility density improved model performance after developed land was already included.

### 5.9 Robustness, Reliability, and Scale Tests

Additional checks were added based on advisor feedback:

1. Hotspot thresholds were varied across top 5%, top 10%, and top 20%.
2. Low-confidence stations were excluded in a separate reliability scenario.
3. Observation-count weighting was tested using square-root and log weights.
4. NOAA annual New Jersey precipitation was joined as an initial rainfall factor.
5. Station-centered land-use buffers were calculated at 500 m, 1 km, and 5 km.
6. Simplified regression models were compared to identify combinations with VIF below 5.
7. EPA ICIS-NPDES DMR flow/load records were downloaded from ECHO, summarized by permit, normalized, matched to NJPDES facility points, and diagnosed for coverage gaps.
8. DMR-linked discharge metrics were summarized by watershed and facility type.
9. NHD flowlines were downloaded for the New Jersey study area and joined to watershed summaries.
10. Matched DMR/NJPDES facility points were snapped to the nearest NHD flowline to create outfall proxy points for map display.
11. Watershed-centroid rainfall, watershed-shape metrics, and an upstream facility-density proxy were added as additional explanatory factors.

---

## 6. Results

### 6.1 Station-Level Hotspots

The station-level analysis identified hundreds of nitrate hotspot stations. Hotspot stations were not evenly distributed across the study area, suggesting that nitrate pollution patterns have strong spatial structure.

### 6.2 Watershed Hotspot Patterns

Several watersheds showed especially high hotspot rates and mean nitrate concentrations. Lower Passaic and Saddle and Hackensack/Hudson/Pascack were important hotspot watersheds with high developed land percentages. Maurice/Salem/Cohansey also showed elevated hotspot rate but had a different land-use pattern, including more agriculture and wetlands.

### 6.3 Land Use Association

The land use analysis found that developed land percentage had a stronger positive association with nitrate hotspot metrics than agriculture percentage. This suggests that in this New Jersey watershed-level dataset, nitrate hotspots are more closely aligned with urban/developed watershed conditions than with agricultural land alone.

### 6.4 NJPDES Facility Association

NJPDES facility density and industrial stormwater facility density were also associated with nitrate hotspot patterns in simple correlation analysis. However, facility density was also strongly connected to developed/urban watersheds, creating the possibility that facility density partly reflects broader urban land use rather than acting as an independent driver.

### 6.5 Multivariable Regression Results

For hotspot rate:

- Land use only adjusted R2: 0.2685
- Developed land + total facility density adjusted R2: 0.2575

For mean nitrate:

- Land use only adjusted R2: 0.4495
- Developed land + total facility density adjusted R2: 0.4155

For mean p90 nitrate:

- Land use only adjusted R2: 0.3388
- Combined extended model adjusted R2: 0.4929

These results suggest that adding facility density did not clearly improve model performance for hotspot rate or mean nitrate after developed land was included. Facility variables may be more informative for upper-tail nitrate conditions such as p90 nitrate, but this result should be treated cautiously.

### 6.6 Multicollinearity

The VIF analysis showed severe multicollinearity among facility-density predictors:

- facility_density_per_100_km2: VIF = 3198.30 (high multicollinearity)
- industrial_stormwater_density_per_100_km2: VIF = 2513.90 (high multicollinearity)
- stormwater_or_surface_density_per_100_km2: VIF = 79.33 (high multicollinearity)
- septic_groundwater_density_per_100_km2: VIF = 22.44 (high multicollinearity)
- groundwater_discharge_density_per_100_km2: VIF = 20.74 (high multicollinearity)

This means the regression coefficients should not be interpreted as independent causal effects. Many predictors overlap spatially, especially total facility density, industrial stormwater density, and developed land.

### 6.7 Hotspot Threshold Robustness

The threshold sensitivity analysis compared top 5%, top 10%, and top 20% hotspot definitions:

- top_5pct: 208 hotspot stations; top watersheds = Hackensack, Hudson, and Pascack; Lower Passaic and Saddle; Maurice, Salem, and Cohansey; Millstone; Lower Raritan, South River, and Lawrence
- top_10pct: 410 hotspot stations; top watersheds = Lower Passaic and Saddle; Hackensack, Hudson, and Pascack; Maurice, Salem, and Cohansey; Millstone; Lower Delaware
- top_20pct: 807 hotspot stations; top watersheds = Lower Passaic and Saddle; North and South Branch Raritan; Maurice, Salem, and Cohansey; Hackensack, Hudson, and Pascack; Lower Delaware

The top-20% threshold had a top-five watershed Jaccard similarity of 0.6667 compared with the top-10% baseline. This indicates that the exact number of hotspot stations changes with the threshold, but the main hotspot regions remain substantially similar.

### 6.8 Confidence Filtering and Weighting

The reliability analysis compared all stations, high/medium-confidence stations only, square-root observation-count weighting, and log observation-count weighting. This directly tests whether the main spatial pattern is driven only by low-observation stations. The website now displays these scenarios side by side so that hotspot rankings can be compared visually.

### 6.9 Rainfall Factor

NOAA statewide New Jersey annual precipitation was joined to yearly nitrate summaries. The rainfall result was weak:

- Pearson r between annual precipitation and annual mean nitrate: 0.1721
- Spearman r between annual precipitation and annual mean nitrate: 0.1556
- Matched years: 26

This suggests that annual statewide rainfall alone is not a stronger predictor than developed land in the current analysis. More detailed rainfall analysis should use station-level or watershed-level precipitation, storm-event timing, and lagged rainfall.

### 6.10 Discharge, Rainfall, Hydrology, and Upstream Proxy

Step 20 adds advisor-requested factors beyond land use and facility density. EPA ICIS-NPDES DMR records were summarized by permit, and the discharge parser loaded `mean_dmr_flow_mgd` from that summary. The current normalized permit join matched 32 of 3574 NJPDES facility points across 13 watersheds, with a facility-level match rate of 0.8954%. This low match rate is now explicitly diagnosed: many facility points use NJG general-permit IDs, while DMR records are summarized at facility-specific permit IDs.

DMR permit matching diagnostics:

- NJ0 / residuals_or_recycling: 21 matched of 180 facilities (11.67%)
- NJ0 / groundwater_discharge: 11 matched of 399 facilities (2.76%)
- NJG / industrial_stormwater: 0 matched of 2037 facilities (0.00%)
- NJG / septic_groundwater: 0 matched of 581 facilities (0.00%)
- NJG / stormwater_or_surface: 0 matched of 227 facilities (0.00%)
- NJG / construction_or_permit: 0 matched of 117 facilities (0.00%)
- NJG / mining_quarrying: 0 matched of 17 facilities (0.00%)
- NJG / residuals_or_recycling: 0 matched of 15 facilities (0.00%)

Outfall location status from Step 20: not_available_in_local_inputs. Flowline network status from Step 20: not_available_in_local_inputs. Step 21 then adds a map-ready hydrography layer and snapped outfall proxies: 12925 NHD flowline segments intersect the study watersheds, 47 DMR-linked facilities were snapped to their nearest NHD flowline, and the median snap distance is 518.94 m. The current coordinate status is `snapped_proxy_generated` because these are hydrologically improved proxies, not observed regulatory outfall coordinates.

The strongest additional-factor correlations were:

- mean_facility_nitrogen_load vs hotspot_rate_percent: Pearson r = -0.8442, Spearman r = -0.9000, n = 5
- mean_facility_nitrogen_load vs mean_nitrate_mg_L: Pearson r = -0.7658, Spearman r = -0.8000, n = 5
- mean_facility_nitrogen_load vs mean_p90_nitrate_mg_L: Pearson r = -0.7434, Spearman r = -0.9000, n = 5
- upgradient_facility_density_proxy_per_100_km2 vs mean_p90_nitrate_mg_L: Pearson r = 0.6304, Spearman r = 0.6714, n = 21
- upgradient_facility_density_proxy_per_100_km2 vs mean_nitrate_mg_L: Pearson r = 0.5615, Spearman r = 0.6143, n = 21
- p90_annual_precip_inches vs hotspot_rate_percent: Pearson r = 0.5613, Spearman r = 0.5339, n = 21

In the additional-factor regression comparison, the developed + agriculture + discharge model had adjusted R2 = 0.3693 for hotspot rate and adjusted R2 = 0.5023 for mean nitrate. These values should be interpreted as exploratory because the discharge factor is available only for matched permits. The pipeline now separates permit-matching coverage from scientific interpretation, so a low DMR match rate is visible instead of being treated as a completed causal exposure layer.

### 6.11 Hydrography and Snapped Outfall Proxy Visualization

The website now includes a hydrography/outfall map at `/maps/hydrography_outfall_context_map.html`. This map shows watershed boundaries, NHD flowlines, DMR-linked snapped outfall proxies, and orange snap-distance connectors back to the original NJPDES facility points. The snapped proxy layer is designed for visual source-context screening, not regulatory outfall confirmation.

Top snapped outfall proxy examples:

- NJ0002895 / STAVOLA CONSTRUCTION MATERIALS: snapped 87.9 m to Middle Brook in Lower Raritan, South River, and Lawrence
- NJ0001228 / FANWOOD CRUSHED STONE CO: snapped 149.4 m to Green Brook in Lower Raritan, South River, and Lawrence
- NJ0005444 / B L ENGLAND GENERATING STATION: snapped 165.3 m to an unnamed NHD flowline in Great Egg Harbor
- NJ0022845 / HARRISON BROOK STP: snapped 169.8 m to Dead River in Upper Passaic, Whippany, and Rockaway
- NJ0144177 / ROCK AVENUE TRANSFER STATION: snapped 220.2 m to an unnamed NHD flowline in Lower Raritan, South River, and Lawrence
- NJ0024694 / MONMOUTH CNTY BAYSHORE OUTFALL AUTHORITY: snapped 229.5 m to an unnamed NHD flowline in Monmouth

Watersheds with the largest downloaded NHD flowline coverage:

- Maurice, Salem, and Cohansey: 2216 segments, 2057.6 km
- Barnegat Bay: 1879 segments, 1329.4 km
- Upper Delaware: 979 segments, 1324.9 km
- Mullica: 1419 segments, 1246.2 km
- North and South Branch Raritan: 480 segments, 830.4 km
- Great Egg Harbor: 419 segments, 727.8 km

### 6.12 Buffer-Based Land Use Scale

Station-centered buffer analysis was added at 500 m, 1 km, and 5 km. The strongest station-buffer association with mean nitrate was agriculture_percent at 5000 m, with Pearson r = 0.2086. This means local land-use context matters, but the buffer-scale correlations are weaker than the watershed-level developed-land signal. The current result supports keeping both watershed-scale and station-buffer-scale views in the website.

### 6.13 Simplified Low-VIF Model Comparison

Simplified models were added to avoid the severe VIF problem found in the larger facility-density model:

- Hotspot rate, developed-only R2: 0.3226
- Hotspot rate, developed + agriculture R2: 0.3417
- Mean nitrate, developed + agriculture adjusted R2: 0.4495
- Hotspot rate, developed + industrial stormwater max VIF: 5.7315

The simplified results show that developed-only or developed + agriculture models keep VIF below 5, while adding industrial stormwater density pushes VIF above the preferred threshold. This supports using simpler independent-variable combinations when the goal is interpretable regression rather than maximum in-sample fit.

---

## 7. Discussion

The overall research narrative is that nitrate hotspots in New Jersey are spatially structured and more concentrated in certain watersheds. Developed land appears to be the most stable watershed-level predictor across the analysis. This does not mean developed land directly causes nitrate pollution by itself. Instead, developed land may represent a combination of urban stormwater runoff, wastewater infrastructure, impervious surfaces, industrial activity, population density, and monitoring patterns.

NJPDES facility density is still important because it helps describe the human infrastructure and regulated discharge landscape. However, after controlling for developed land, facility density does not clearly add independent explanatory value for hotspot rate or mean nitrate. This suggests that facility density may partly act as a proxy for urbanized watersheds.

The p90 nitrate results are more complex. Facility-related variables appeared more useful for explaining high-end nitrate conditions than average nitrate. This may indicate that regulated facilities, stormwater systems, or localized discharge pathways are more relevant during high-concentration events. The added DMR flow summary, match diagnostics, downloaded NHD flowlines, and snapped outfall proxy map help test this idea without overstating the result: permit-level flow and map-ready proxy points are available for the matched subset, while exact regulatory outfall coordinates still require an outfall-coordinate layer or permit-outfall crosswalk.

---

## 8. Limitations

1. The analysis is watershed-level, so it cannot identify exact pollution sources.
2. The study shows association, not causation.
3. Some watersheds have more monitoring stations than others, creating possible sampling bias.
4. EPA DMR flow/load data are now included and diagnosed, but only 32 of 3574 NJPDES facility points match the local DMR permit summary.
5. Facility density may overlap with developed land, causing severe multicollinearity.
6. Hydrology is improved with 12925 downloaded NHD flowlines and 47 snapped outfall proxies, but these proxies do not replace exact regulatory outfall coordinates or full upstream/downstream network tracing.
7. The regression sample size is small because there are only 21 watersheds.

---

## 9. Future Work

Future analysis should:

1. Add an EPA/NJDEP outfall-coordinate layer or permit-outfall crosswalk so snapped proxy points can be replaced with observed outfall coordinates.
2. Add catchment-level routing or NHDPlus VAA routing so upstream/downstream tracing can replace nearest-flowline snapping.
3. Separate point-source facilities from stormwater-related facilities more carefully.
4. Improve rainfall analysis with event-level and lagged precipitation instead of annual summaries.
5. Control for monitoring density and station confidence.
6. Use smaller spatial units such as subwatersheds or catchments.
7. Compare nitrate trends before and after major facility or land-use changes.
8. Extend the interactive website so selecting a watershed filters nitrate stations, land use, DMR permit features, snapped outfall proxies, and flowlines together.

---

## 10. Conclusion

This project shows that nitrate hotspots near New Jersey are not randomly distributed. Developed watersheds tend to show higher nitrate hotspot rates and mean nitrate concentrations. Threshold, confidence, weighting, buffer-scale checks, DMR discharge summaries, DMR match diagnostics, downloaded NHD flowlines, snapped outfall proxies, rainfall factors, and hydrology/upstream proxies support the robustness of the main spatial pattern while also showing that source attribution remains difficult. NJPDES facility density is associated with nitrate patterns, but multivariable analysis suggests that much of this relationship overlaps with developed land. Facility and discharge variables may be more relevant for high-end nitrate events, but stronger causal claims require observed outfall coordinates, catchment routing, rainfall timing, and upstream source analysis.

The project demonstrates a complete research workflow from raw public water-quality data to hotspot detection, spatial analysis, land-use overlay, facility-density analysis, regression modeling, and interactive website communication.

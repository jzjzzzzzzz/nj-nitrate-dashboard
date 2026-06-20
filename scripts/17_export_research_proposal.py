from pathlib import Path
import json
import pandas as pd


# ============================================================
# Step 17: Export Research Proposal / Research Summary
# Purpose:
#   Convert the full nitrate hotspot analysis into a formal
#   proposal-style research output for website display.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data" / "processed"
DASHBOARD_DIR = BASE_DIR / "output" / "dashboard"
PROPOSAL_DIR = BASE_DIR / "output" / "proposal"
LOG_DIR = BASE_DIR / "output" / "logs"

PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

OUT_MD = PROPOSAL_DIR / "nj_nitrate_research_proposal.md"
OUT_HTML = PROPOSAL_DIR / "nj_nitrate_research_proposal.html"
OUT_SUMMARY_JSON = DASHBOARD_DIR / "research_proposal_summary.json"
LOG_PATH = LOG_DIR / "17_export_research_proposal_log.txt"


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def read_csv_if_exists(path):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def read_json_if_exists(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def fmt(value, digits=4):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "N/A"


def get_model_value(model_df, target_metric, model_name, column):
    if model_df.empty:
        return "N/A"

    sub = model_df[
        (model_df["target_metric"] == target_metric)
        & (model_df["model_name"] == model_name)
    ]

    if sub.empty:
        return "N/A"

    return fmt(sub.iloc[0].get(column), 4)


def build_proposal_markdown():
    summary = read_json_if_exists(DASHBOARD_DIR / "summary_cards.json")
    watershed_df = read_csv_if_exists(DATA_DIR / "watershed_summary.csv")
    land_use_corr_df = read_csv_if_exists(DATA_DIR / "land_use_nitrate_correlation.csv")
    facility_corr_df = read_csv_if_exists(DATA_DIR / "facility_nitrate_correlation.csv")
    model_df = read_csv_if_exists(DATA_DIR / "multivariable_model_comparison.csv")
    vif_df = read_csv_if_exists(DATA_DIR / "multivariable_model_vif.csv")
    threshold_df = read_csv_if_exists(DATA_DIR / "hotspot_threshold_robustness.csv")
    simplified_model_df = read_csv_if_exists(DATA_DIR / "simplified_model_vif_comparison.csv")
    rainfall_df = read_csv_if_exists(DATA_DIR / "rainfall_nitrate_yearly_correlation.csv")
    buffer_corr_df = read_csv_if_exists(DATA_DIR / "station_buffer_land_use_correlation.csv")
    additional_corr_df = read_csv_if_exists(DATA_DIR / "additional_factor_nitrate_correlation.csv")
    additional_model_df = read_csv_if_exists(DATA_DIR / "additional_factor_model_comparison.csv")
    discharge_status_df = read_csv_if_exists(DATA_DIR / "discharge_volume_status.csv")
    discharge_match_df = read_csv_if_exists(DATA_DIR / "discharge_permit_match_summary.csv")
    hydro_status = read_json_if_exists(DASHBOARD_DIR / "hydrography_outfall_status.json")
    snapped_proxy_df = read_csv_if_exists(DATA_DIR / "dmr_outfall_snapped_proxy_points.csv")
    hydro_flowline_df = read_csv_if_exists(DATA_DIR / "watershed_hydrography_flowline_summary.csv")

    total_stations = "3,658"
    hotspot_stations = "411"
    high_confidence = "76"

    if isinstance(summary, dict):
        total_stations = summary.get("total_stations", total_stations)
        hotspot_stations = summary.get("hotspot_stations", hotspot_stations)
        high_confidence = summary.get("high_confidence", high_confidence)

    hotspot_land_adj = get_model_value(
        model_df,
        "hotspot_rate_percent",
        "land_use_only",
        "adjusted_r2"
    )

    hotspot_facility_adj = get_model_value(
        model_df,
        "hotspot_rate_percent",
        "developed_plus_total_facility",
        "adjusted_r2"
    )

    mean_land_adj = get_model_value(
        model_df,
        "mean_nitrate_mg_L",
        "land_use_only",
        "adjusted_r2"
    )

    mean_facility_adj = get_model_value(
        model_df,
        "mean_nitrate_mg_L",
        "developed_plus_total_facility",
        "adjusted_r2"
    )

    p90_land_adj = get_model_value(
        model_df,
        "mean_p90_nitrate_mg_L",
        "land_use_only",
        "adjusted_r2"
    )

    p90_extended_adj = get_model_value(
        model_df,
        "mean_p90_nitrate_mg_L",
        "combined_extended",
        "adjusted_r2"
    )

    hotspot_developed_only_r2 = get_model_value(
        simplified_model_df,
        "hotspot_rate_percent",
        "developed_only",
        "r2"
    )

    hotspot_developed_agriculture_r2 = get_model_value(
        simplified_model_df,
        "hotspot_rate_percent",
        "developed_agriculture",
        "r2"
    )

    hotspot_developed_industrial_vif = get_model_value(
        simplified_model_df,
        "hotspot_rate_percent",
        "developed_industrial",
        "max_vif"
    )

    mean_developed_agriculture_adj = get_model_value(
        simplified_model_df,
        "mean_nitrate_mg_L",
        "developed_agriculture",
        "adjusted_r2"
    )

    threshold_text = "Alternative hotspot-threshold results were not available."
    threshold_20_jaccard = "N/A"

    if not threshold_df.empty:
        threshold_lines = []
        for _, row in threshold_df.iterrows():
            threshold_lines.append(
                f"- {row.get('threshold')}: {int(row.get('hotspot_station_count', 0))} hotspot stations; "
                f"top watersheds = {row.get('top5_watersheds', 'N/A')}"
            )

        sub20 = threshold_df[threshold_df["threshold"] == "top_20pct"]
        if not sub20.empty:
            threshold_20_jaccard = fmt(sub20.iloc[0].get("top5_watershed_jaccard_vs_10pct"), 4)

        threshold_text = "\n".join(threshold_lines)

    rainfall_pearson = "N/A"
    rainfall_spearman = "N/A"
    rainfall_n = "N/A"

    if not rainfall_df.empty and "pearson_r_precip_vs_mean_nitrate" in rainfall_df.columns:
        rainfall_pearson = fmt(rainfall_df.iloc[0].get("pearson_r_precip_vs_mean_nitrate"), 4)
        rainfall_spearman = fmt(rainfall_df.iloc[0].get("spearman_r_precip_vs_mean_nitrate"), 4)
        rainfall_n = str(len(rainfall_df))

    discharge_status = "not_available"
    discharge_matched_facilities = "0"
    discharge_matched_watersheds = "0"
    discharge_total_facilities = "0"
    discharge_facility_match_rate = "N/A"
    discharge_permit_match_rate = "N/A"
    discharge_matched_unique_permits = "0"
    discharge_dmr_permit_count = "0"
    discharge_general_permit_facilities = "0"
    outfall_location_status = "N/A"
    flowline_network_status = "N/A"
    discharge_value_column = "N/A"

    if not discharge_status_df.empty:
        discharge_row = discharge_status_df.iloc[0]
        discharge_status = str(discharge_row.get("status", discharge_status))
        discharge_matched_facilities = str(discharge_row.get("matched_facilities", discharge_matched_facilities))
        discharge_matched_watersheds = str(discharge_row.get("matched_watersheds", discharge_matched_watersheds))
        discharge_total_facilities = str(discharge_row.get("total_facilities", discharge_total_facilities))
        discharge_facility_match_rate = fmt(discharge_row.get("facility_match_rate_percent"), 4)
        discharge_permit_match_rate = fmt(discharge_row.get("permit_match_rate_percent"), 4)
        discharge_matched_unique_permits = str(discharge_row.get("matched_unique_permits", discharge_matched_unique_permits))
        discharge_dmr_permit_count = str(discharge_row.get("dmr_permit_count", discharge_dmr_permit_count))
        discharge_general_permit_facilities = str(discharge_row.get("general_permit_facilities", discharge_general_permit_facilities))
        outfall_location_status = str(discharge_row.get("outfall_location_status", outfall_location_status))
        flowline_network_status = str(discharge_row.get("flowline_network_status", flowline_network_status))
        discharge_value_column = str(discharge_row.get("value_column", discharge_value_column))

    discharge_match_note = (
        f"Matched {discharge_matched_facilities} of {discharge_total_facilities} NJPDES facility points "
        f"to DMR flow summaries ({discharge_facility_match_rate}% by facility). "
        f"The local DMR summary contains {discharge_dmr_permit_count} permits; "
        f"{discharge_matched_unique_permits} normalized facility permit IDs matched it. "
        f"{discharge_general_permit_facilities} facility points use NJG general-permit IDs, which usually do not "
        "map one-to-one to facility-specific DMR rows."
    )

    discharge_match_text = "DMR permit match diagnostics were not available."
    if not discharge_match_df.empty:
        match_rows = discharge_match_df.sort_values(
            ["matched_facilities", "total_facilities"],
            ascending=[False, False],
        ).head(8)
        lines = []
        for _, row in match_rows.iterrows():
            lines.append(
                f"- {row.get('permit_prefix')} / {row.get('facility_type_group')}: "
                f"{int(row.get('matched_facilities', 0))} matched of "
                f"{int(row.get('total_facilities', 0))} facilities "
                f"({fmt(row.get('match_rate_percent'), 2)}%)"
            )
        discharge_match_text = "\n".join(lines)

    hydro_status_row = {}
    if isinstance(hydro_status, list) and hydro_status:
        hydro_status_row = hydro_status[0]
    elif isinstance(hydro_status, dict):
        hydro_status_row = hydro_status

    snapped_outfall_proxy_count = str(hydro_status_row.get("snapped_outfall_proxy_count", "0"))
    median_snap_distance_m = fmt(hydro_status_row.get("median_snap_distance_m"), 2)
    flowline_segment_count = str(hydro_status_row.get("flowline_segment_count", "0"))
    flowline_network_status_latest = str(hydro_status_row.get("flowline_network_status", flowline_network_status))
    outfall_coordinate_status_latest = str(hydro_status_row.get("outfall_coordinate_status", outfall_location_status))
    outfall_proxy_used = str(hydro_status_row.get("outfall_proxy_used", "N/A"))
    hydro_map_path = str(hydro_status_row.get("map_path", "/maps/hydrography_outfall_context_map.html"))

    snapped_proxy_text = "Snapped outfall proxy results were not available."
    if not snapped_proxy_df.empty:
        top_proxy = snapped_proxy_df.sort_values("snap_distance_m").head(6)
        lines = []
        for _, row in top_proxy.iterrows():
            lines.append(
                f"- {row.get('permit_id_clean')} / {row.get('facility_name')}: "
                f"snapped {fmt(row.get('snap_distance_m'), 1)} m to "
                f"{row.get('nearest_flowline_name') if pd.notna(row.get('nearest_flowline_name')) and str(row.get('nearest_flowline_name')).strip() else 'an unnamed NHD flowline'} "
                f"in {row.get('watershed_name')}"
            )
        snapped_proxy_text = "\n".join(lines)

    flowline_top_text = "Watershed flowline summaries were not available."
    if not hydro_flowline_df.empty:
        top_flow = hydro_flowline_df.sort_values("flowline_total_length_km", ascending=False).head(6)
        lines = []
        for _, row in top_flow.iterrows():
            lines.append(
                f"- {row.get('watershed_name')}: "
                f"{int(row.get('flowline_segment_count', 0))} segments, "
                f"{fmt(row.get('flowline_total_length_km'), 1)} km"
            )
        flowline_top_text = "\n".join(lines)

    discharge_hotspot_adj = get_model_value(
        additional_model_df,
        "hotspot_rate_percent",
        "developed_agriculture_discharge",
        "adjusted_r2"
    )

    discharge_mean_adj = get_model_value(
        additional_model_df,
        "mean_nitrate_mg_L",
        "developed_agriculture_discharge",
        "adjusted_r2"
    )

    top_additional_factor_text = "Additional factor correlation results were not available."

    if not additional_corr_df.empty and "pearson_r" in additional_corr_df.columns:
        additional_corr_df["pearson_abs"] = pd.to_numeric(additional_corr_df["pearson_r"], errors="coerce").abs()
        top_additional = additional_corr_df.sort_values("pearson_abs", ascending=False).head(6)
        lines = []
        for _, row in top_additional.iterrows():
            lines.append(
                f"- {row.get('factor_metric')} vs {row.get('nitrate_metric')}: "
                f"Pearson r = {fmt(row.get('pearson_r'), 4)}, "
                f"Spearman r = {fmt(row.get('spearman_r'), 4)}, n = {int(row.get('n', 0))}"
            )
        top_additional_factor_text = "\n".join(lines)

    buffer_best_text = "Buffer land-use correlation results were not available."
    buffer_best_radius = "N/A"
    buffer_best_metric = "N/A"
    buffer_best_r = "N/A"

    if not buffer_corr_df.empty and "pearson_r" in buffer_corr_df.columns:
        buffer_corr_df["pearson_abs"] = pd.to_numeric(buffer_corr_df["pearson_r"], errors="coerce").abs()
        mean_buffer = buffer_corr_df[buffer_corr_df["nitrate_metric"] == "mean_nitrate_mg_L"].copy()

        if not mean_buffer.empty:
            best = mean_buffer.sort_values("pearson_abs", ascending=False).iloc[0]
            buffer_best_radius = str(int(best.get("buffer_radius_m")))
            buffer_best_metric = str(best.get("land_use_metric"))
            buffer_best_r = fmt(best.get("pearson_r"), 4)
            buffer_best_text = (
                f"The strongest station-buffer association with mean nitrate was {buffer_best_metric} "
                f"at {buffer_best_radius} m, with Pearson r = {buffer_best_r}."
            )

    top_vif_text = "VIF results were not available."

    if not vif_df.empty and "vif" in vif_df.columns:
        vif_df["vif"] = pd.to_numeric(vif_df["vif"], errors="coerce")
        top_vif = vif_df.sort_values("vif", ascending=False).head(5)

        lines = []
        for _, row in top_vif.iterrows():
            lines.append(
                f"- {row.get('predictor')}: VIF = {fmt(row.get('vif'), 2)} "
                f"({row.get('interpretation', 'N/A')})"
            )

        top_vif_text = "\n".join(lines)

    proposal = f"""# New Jersey Nitrate Hotspot Research Proposal

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

- Total stations: {total_stations}
- Hotspot stations: {hotspot_stations}
- High-confidence stations: {high_confidence}

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

- Land use only adjusted R2: {hotspot_land_adj}
- Developed land + total facility density adjusted R2: {hotspot_facility_adj}

For mean nitrate:

- Land use only adjusted R2: {mean_land_adj}
- Developed land + total facility density adjusted R2: {mean_facility_adj}

For mean p90 nitrate:

- Land use only adjusted R2: {p90_land_adj}
- Combined extended model adjusted R2: {p90_extended_adj}

These results suggest that adding facility density did not clearly improve model performance for hotspot rate or mean nitrate after developed land was included. Facility variables may be more informative for upper-tail nitrate conditions such as p90 nitrate, but this result should be treated cautiously.

### 6.6 Multicollinearity

The VIF analysis showed severe multicollinearity among facility-density predictors:

{top_vif_text}

This means the regression coefficients should not be interpreted as independent causal effects. Many predictors overlap spatially, especially total facility density, industrial stormwater density, and developed land.

### 6.7 Hotspot Threshold Robustness

The threshold sensitivity analysis compared top 5%, top 10%, and top 20% hotspot definitions:

{threshold_text}

The top-20% threshold had a top-five watershed Jaccard similarity of {threshold_20_jaccard} compared with the top-10% baseline. This indicates that the exact number of hotspot stations changes with the threshold, but the main hotspot regions remain substantially similar.

### 6.8 Confidence Filtering and Weighting

The reliability analysis compared all stations, high/medium-confidence stations only, square-root observation-count weighting, and log observation-count weighting. This directly tests whether the main spatial pattern is driven only by low-observation stations. The website now displays these scenarios side by side so that hotspot rankings can be compared visually.

### 6.9 Rainfall Factor

NOAA statewide New Jersey annual precipitation was joined to yearly nitrate summaries. The rainfall result was weak:

- Pearson r between annual precipitation and annual mean nitrate: {rainfall_pearson}
- Spearman r between annual precipitation and annual mean nitrate: {rainfall_spearman}
- Matched years: {rainfall_n}

This suggests that annual statewide rainfall alone is not a stronger predictor than developed land in the current analysis. More detailed rainfall analysis should use station-level or watershed-level precipitation, storm-event timing, and lagged rainfall.

### 6.10 Discharge, Rainfall, Hydrology, and Upstream Proxy

Step 20 adds advisor-requested factors beyond land use and facility density. EPA ICIS-NPDES DMR records were summarized by permit, and the discharge parser loaded `{discharge_value_column}` from that summary. The current normalized permit join matched {discharge_matched_facilities} of {discharge_total_facilities} NJPDES facility points across {discharge_matched_watersheds} watersheds, with a facility-level match rate of {discharge_facility_match_rate}%. This low match rate is now explicitly diagnosed: many facility points use NJG general-permit IDs, while DMR records are summarized at facility-specific permit IDs.

DMR permit matching diagnostics:

{discharge_match_text}

Outfall location status from Step 20: {outfall_location_status}. Flowline network status from Step 20: {flowline_network_status}. Step 21 then adds a map-ready hydrography layer and snapped outfall proxies: {flowline_segment_count} NHD flowline segments intersect the study watersheds, {snapped_outfall_proxy_count} DMR-linked facilities were snapped to their nearest NHD flowline, and the median snap distance is {median_snap_distance_m} m. The current coordinate status is `{outfall_coordinate_status_latest}` because these are hydrologically improved proxies, not observed regulatory outfall coordinates.

The strongest additional-factor correlations were:

{top_additional_factor_text}

In the additional-factor regression comparison, the developed + agriculture + discharge model had adjusted R2 = {discharge_hotspot_adj} for hotspot rate and adjusted R2 = {discharge_mean_adj} for mean nitrate. These values should be interpreted as exploratory because the discharge factor is available only for matched permits. The pipeline now separates permit-matching coverage from scientific interpretation, so a low DMR match rate is visible instead of being treated as a completed causal exposure layer.

### 6.11 Hydrography and Snapped Outfall Proxy Visualization

The website now includes a hydrography/outfall map at `{hydro_map_path}`. This map shows watershed boundaries, NHD flowlines, DMR-linked snapped outfall proxies, and orange snap-distance connectors back to the original NJPDES facility points. The snapped proxy layer is designed for visual source-context screening, not regulatory outfall confirmation.

Top snapped outfall proxy examples:

{snapped_proxy_text}

Watersheds with the largest downloaded NHD flowline coverage:

{flowline_top_text}

### 6.12 Buffer-Based Land Use Scale

Station-centered buffer analysis was added at 500 m, 1 km, and 5 km. {buffer_best_text} This means local land-use context matters, but the buffer-scale correlations are weaker than the watershed-level developed-land signal. The current result supports keeping both watershed-scale and station-buffer-scale views in the website.

### 6.13 Simplified Low-VIF Model Comparison

Simplified models were added to avoid the severe VIF problem found in the larger facility-density model:

- Hotspot rate, developed-only R2: {hotspot_developed_only_r2}
- Hotspot rate, developed + agriculture R2: {hotspot_developed_agriculture_r2}
- Mean nitrate, developed + agriculture adjusted R2: {mean_developed_agriculture_adj}
- Hotspot rate, developed + industrial stormwater max VIF: {hotspot_developed_industrial_vif}

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
4. EPA DMR flow/load data are now included and diagnosed, but only {discharge_matched_facilities} of {discharge_total_facilities} NJPDES facility points match the local DMR permit summary.
5. Facility density may overlap with developed land, causing severe multicollinearity.
6. Hydrology is improved with {flowline_segment_count} downloaded NHD flowlines and {snapped_outfall_proxy_count} snapped outfall proxies, but these proxies do not replace exact regulatory outfall coordinates or full upstream/downstream network tracing.
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
"""

    summary_json = {
        "title": "New Jersey Nitrate Hotspot Research Proposal",
        "main_finding": "Developed land remains the most stable watershed-level predictor after threshold, confidence, weighting, rainfall, buffer-scale, DMR discharge, hydrology/upstream proxy, and low-VIF model checks. Facility density and matched DMR flow are useful exploratory factors, but they do not yet prove independent causal effects after developed land is included.",
        "hotspot_land_use_adjusted_r2": hotspot_land_adj,
        "hotspot_facility_adjusted_r2": hotspot_facility_adj,
        "mean_land_use_adjusted_r2": mean_land_adj,
        "mean_facility_adjusted_r2": mean_facility_adj,
        "p90_land_use_adjusted_r2": p90_land_adj,
        "p90_extended_adjusted_r2": p90_extended_adj,
        "threshold_20_top5_watershed_jaccard_vs_10pct": threshold_20_jaccard,
        "rainfall_pearson_r": rainfall_pearson,
        "rainfall_spearman_r": rainfall_spearman,
        "discharge_status": discharge_status,
        "discharge_matched_facilities": discharge_matched_facilities,
        "discharge_matched_watersheds": discharge_matched_watersheds,
        "discharge_total_facilities": discharge_total_facilities,
        "discharge_facility_match_rate_percent": discharge_facility_match_rate,
        "discharge_permit_match_rate_percent": discharge_permit_match_rate,
        "discharge_matched_unique_permits": discharge_matched_unique_permits,
        "discharge_dmr_permit_count": discharge_dmr_permit_count,
        "discharge_general_permit_facilities": discharge_general_permit_facilities,
        "outfall_location_status": outfall_location_status,
        "flowline_network_status": flowline_network_status,
        "latest_outfall_coordinate_status": outfall_coordinate_status_latest,
        "latest_flowline_network_status": flowline_network_status_latest,
        "snapped_outfall_proxy_count": snapped_outfall_proxy_count,
        "median_snap_distance_m": median_snap_distance_m,
        "flowline_segment_count": flowline_segment_count,
        "outfall_proxy_used": outfall_proxy_used,
        "hydrography_map_path": hydro_map_path,
        "discharge_match_note": discharge_match_note,
        "discharge_hotspot_adjusted_r2": discharge_hotspot_adj,
        "discharge_mean_adjusted_r2": discharge_mean_adj,
        "buffer_best_radius_m": buffer_best_radius,
        "buffer_best_metric": buffer_best_metric,
        "buffer_best_pearson_r": buffer_best_r,
        "hotspot_developed_only_r2": hotspot_developed_only_r2,
        "hotspot_developed_agriculture_r2": hotspot_developed_agriculture_r2,
        "mean_developed_agriculture_adjusted_r2": mean_developed_agriculture_adj,
        "caution": "Watershed-level association only; not causal evidence."
    }

    return proposal, summary_json


def markdown_to_simple_html(markdown_text):
    html_lines = []

    for line in markdown_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped.startswith("---"):
            html_lines.append("<hr>")
        elif stripped == "":
            html_lines.append("")
        else:
            line_html = stripped.replace("**", "")
            html_lines.append(f"<p>{line_html}</p>")

    body = "\n".join(html_lines)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>New Jersey Nitrate Hotspot Research Proposal</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            max-width: 980px;
            margin: 0 auto;
            padding: 36px;
            color: #1f2937;
            line-height: 1.65;
            background: #ffffff;
        }}

        h1 {{
            color: #0f172a;
            font-size: 34px;
            line-height: 1.2;
            margin-bottom: 18px;
        }}

        h2 {{
            color: #1d4ed8;
            border-bottom: 2px solid #dbeafe;
            padding-bottom: 6px;
            margin-top: 34px;
        }}

        h3 {{
            color: #0f766e;
            margin-top: 24px;
        }}

        p {{
            font-size: 16px;
        }}

        li {{
            margin-bottom: 8px;
        }}

        hr {{
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 28px 0;
        }}
    </style>
</head>
<body>
{body}
</body>
</html>
"""

    return html


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    log("========== Step 17: Export Research Proposal ==========")

    proposal_md, summary_json = build_proposal_markdown()
    proposal_html = markdown_to_simple_html(proposal_md)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(proposal_md)

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(proposal_html)

    with open(OUT_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    log(f"[EXPORT] {OUT_MD}")
    log(f"[EXPORT] {OUT_HTML}")
    log(f"[EXPORT] {OUT_SUMMARY_JSON}")
    log("Step 17 finished successfully.")


if __name__ == "__main__":
    main()

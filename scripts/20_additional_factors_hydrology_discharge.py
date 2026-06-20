import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

WATERSHED_PATH = BASE_DIR / "data" / "external" / "watershed" / "nj_watershed_management_areas.geojson"
WASTEWATER_PATH = BASE_DIR / "data" / "external" / "wastewater" / "New_Jersey_Pollution_Discharge_Elimination_System_(NJPDES)_Regulated_Facility_Locations.shp"
WATERSHED_JOINED_PATH = BASE_DIR / "data" / "processed" / "watershed_land_use_wastewater_nitrate_joined.csv"

DISCHARGE_DIR = BASE_DIR / "data" / "external" / "discharge"
RAINFALL_DIR = BASE_DIR / "data" / "external" / "rainfall" / "open_meteo_watershed_cache"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_FIGURES = BASE_DIR / "output" / "figures"
OUT_LOGS = BASE_DIR / "output" / "logs"
LOG_PATH = OUT_LOGS / "20_additional_factors_hydrology_discharge_log.txt"

OUT_FACTOR_CSV = OUT_PROCESSED / "watershed_additional_factors_joined.csv"
OUT_CORR_CSV = OUT_PROCESSED / "additional_factor_nitrate_correlation.csv"
OUT_MODEL_CSV = OUT_PROCESSED / "additional_factor_model_comparison.csv"
OUT_DISCHARGE_MATCH_CSV = OUT_PROCESSED / "discharge_permit_match_summary.csv"

OUT_FACTOR_JSON = OUT_DASHBOARD / "watershed_additional_factors_joined.json"
OUT_CORR_JSON = OUT_DASHBOARD / "additional_factor_nitrate_correlation.json"
OUT_MODEL_JSON = OUT_DASHBOARD / "additional_factor_model_comparison.json"
OUT_DISCHARGE_MATCH_JSON = OUT_DASHBOARD / "discharge_permit_match_summary.json"

FIG_RAIN = OUT_FIGURES / "watershed_rainfall_vs_mean_nitrate.png"
FIG_CORR = OUT_FIGURES / "additional_factors_correlation.png"
FIG_HYDRO = OUT_FIGURES / "hydrology_proxy_vs_hotspot_rate.png"


def ensure_dirs():
    for path in [DISCHARGE_DIR, RAINFALL_DIR, OUT_PROCESSED, OUT_DASHBOARD, OUT_FIGURES, OUT_LOGS]:
        path.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def clean_name(value):
    return (
        str(value)
        .replace("/", "_")
        .replace("\\", "_")
        .replace(",", "")
        .replace(" ", "_")
        .replace("&", "and")
    )


def normalize_permit_id(value):
    if pd.isna(value):
        return ""

    text = str(value).upper().strip()
    if text.endswith(".0"):
        text = text[:-2]

    return "".join(ch for ch in text if ch.isalnum())


def classify_facility_type(row):
    distype = str(row.get("DISTYPE", "")).upper().strip()
    facility_name = str(row.get("FACILITY", "")).upper().strip()

    if distype == "5G2":
        return "industrial_stormwater"
    if distype == "T1":
        return "septic_groundwater"
    if distype == "GW":
        return "groundwater_discharge"
    if distype == "SM":
        return "stormwater_or_surface"
    if distype in ["RF", "R4"]:
        return "residuals_or_recycling"
    if distype == "CPM":
        return "construction_or_permit"
    if distype == "R13":
        return "mining_quarrying"

    if any(word in facility_name for word in [
        "STP",
        "SEWER",
        "SEWERAGE",
        "WASTEWATER",
        "WWTP",
        "POTW",
        "SANITARY",
        "TREATMENT PLANT",
    ]):
        return "wastewater_treatment"

    if any(word in facility_name for word in [
        "REFINERY",
        "CHEMICAL",
        "METAL",
        "MANUFACTUR",
        "FACTORY",
        "CORP",
        "INC",
        "INDUSTRIAL",
    ]):
        return "industrial_other"

    return "other"


def export_json(df, path):
    clean = df.replace([np.inf, -np.inf], np.nan)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean.where(pd.notna(clean), None).to_dict(orient="records"), f, indent=2)


def pearson(x, y):
    temp = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(temp) < 3 or temp["x"].std(ddof=0) == 0 or temp["y"].std(ddof=0) == 0:
        return None
    return float(temp["x"].corr(temp["y"]))


def spearman(x, y):
    temp = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(temp) < 3:
        return None
    return pearson(temp["x"].rank(method="average"), temp["y"].rank(method="average"))


def ols_fit(X, y):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = X.shape[0]
    p = X.shape[1]
    beta = np.linalg.pinv(X.T @ X) @ X.T @ y
    pred = X @ beta
    resid = y - pred
    sse = float(np.sum(resid ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    r2 = np.nan if sst == 0 else 1 - sse / sst
    adj = np.nan if n <= p else 1 - ((1 - r2) * (n - 1) / (n - p))
    rmse = math.sqrt(sse / n) if n else np.nan
    return {"r2": r2, "adjusted_r2": adj, "rmse": rmse, "n": n, "p": p}


def calculate_vif(df, predictors):
    usable = df[predictors].dropna()
    values = []
    for target in predictors:
        others = [c for c in predictors if c != target]
        if not others:
            values.append(1.0)
            continue
        temp = usable[[target] + others].dropna()
        if len(temp) < len(others) + 3:
            continue
        X = np.column_stack([np.ones(len(temp)), temp[others].values])
        fit = ols_fit(X, temp[target].values)
        r2 = fit["r2"]
        if pd.isna(r2) or r2 >= 1:
            continue
        values.append(1 / (1 - r2))
    return max(values) if values else None


def read_base_data():
    watersheds = gpd.read_file(WATERSHED_PATH)
    wastewater = gpd.read_file(WASTEWATER_PATH)
    joined = pd.read_csv(WATERSHED_JOINED_PATH)

    name_col = "WMA_NAME"
    watersheds = watersheds[[name_col, "WR_NAME", "geometry"]].rename(columns={name_col: "watershed_name"})

    watersheds_wgs = watersheds.to_crs("EPSG:4326")
    watersheds_nj = watersheds.to_crs("EPSG:3424")
    wastewater_nj = wastewater.to_crs("EPSG:3424")

    return watersheds_wgs, watersheds_nj, wastewater_nj, joined


def fetch_watershed_rainfall(watersheds_wgs):
    rows = []
    for _, row in watersheds_wgs.iterrows():
        name = row["watershed_name"]
        centroid = row.geometry.centroid
        lat = round(float(centroid.y), 5)
        lon = round(float(centroid.x), 5)
        cache_path = RAINFALL_DIR / f"{clean_name(name)}_2000_2025.csv"

        if not cache_path.exists():
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": "2000-01-01",
                "end_date": "2025-12-31",
                "daily": "precipitation_sum",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": "America/New_York",
            }
            url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
            log(f"[RAIN] Downloading {name}: {url}")
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                daily = payload.get("daily", {})
                rain_df = pd.DataFrame({
                    "date": daily.get("time", []),
                    "precipitation_inches": daily.get("precipitation_sum", []),
                })
                rain_df.to_csv(cache_path, index=False)
                time.sleep(0.5)
            except Exception as exc:
                log(f"[RAIN] Download failed for {name}: {exc}")
                continue

        rain = pd.read_csv(cache_path)
        rain["date"] = pd.to_datetime(rain["date"], errors="coerce")
        rain["year"] = rain["date"].dt.year
        rain["precipitation_inches"] = pd.to_numeric(rain["precipitation_inches"], errors="coerce")
        annual = (
            rain.dropna(subset=["year", "precipitation_inches"])
            .groupby("year", as_index=False)
            .agg(annual_precip_inches=("precipitation_inches", "sum"))
        )
        rows.append({
            "watershed_name": name,
            "rainfall_source": "Open-Meteo archive API, watershed centroid",
            "rainfall_centroid_lat": lat,
            "rainfall_centroid_lon": lon,
            "rainfall_years": int(len(annual)),
            "mean_annual_precip_inches": round(float(annual["annual_precip_inches"].mean()), 4) if not annual.empty else None,
            "p90_annual_precip_inches": round(float(annual["annual_precip_inches"].quantile(0.9)), 4) if not annual.empty else None,
            "precip_cv": round(float(annual["annual_precip_inches"].std(ddof=0) / annual["annual_precip_inches"].mean()), 4) if len(annual) > 1 and annual["annual_precip_inches"].mean() else None,
        })
    if not rows:
        return pd.DataFrame(columns=[
            "watershed_name",
            "rainfall_source",
            "rainfall_centroid_lat",
            "rainfall_centroid_lon",
            "rainfall_years",
            "mean_annual_precip_inches",
            "p90_annual_precip_inches",
            "precip_cv",
        ])

    return pd.DataFrame(rows)


def hydrology_and_upstream_proxy(watersheds_nj, wastewater_nj):
    rows = []
    facilities = wastewater_nj.copy()
    facilities["x"] = facilities.geometry.x
    facilities["y"] = facilities.geometry.y

    for _, row in watersheds_nj.iterrows():
        geom = row.geometry
        centroid = geom.centroid
        area_km2 = geom.area * 0.09290304 / 1_000_000
        perimeter_km = geom.length * 0.3048006096 / 1000
        compactness = (4 * math.pi * area_km2) / (perimeter_km ** 2) if perimeter_km else None

        same_region = watersheds_nj[watersheds_nj["WR_NAME"] == row["WR_NAME"]].copy()
        same_region_names = set(same_region["watershed_name"])

        # This is a directional screening proxy, not a true NHD flowline upstream trace.
        # It counts facilities north/upgradient of the watershed centroid within the same NJ watershed region.
        try:
            region_geom = same_region.geometry.union_all()
        except AttributeError:
            region_geom = same_region.geometry.unary_union
        region_facilities = facilities[facilities.geometry.within(region_geom)].copy()
        upstream_like = region_facilities[region_facilities["y"] >= centroid.y].copy()

        rows.append({
            "watershed_name": row["watershed_name"],
            "hydro_region": row["WR_NAME"],
            "watershed_area_km2_recomputed": round(float(area_km2), 4),
            "perimeter_km": round(float(perimeter_km), 4),
            "shape_compactness": round(float(compactness), 6) if compactness is not None else None,
            "centroid_x_njft": round(float(centroid.x), 4),
            "centroid_y_njft": round(float(centroid.y), 4),
            "region_watershed_count": int(len(same_region_names)),
            "upgradient_facility_count_proxy": int(len(upstream_like)),
            "upgradient_facility_density_proxy_per_100_km2": round(float(len(upstream_like) / area_km2 * 100), 4) if area_km2 else None,
            "upgradient_proxy_note": "Directional same-region proxy only; not true NHD upstream tracing.",
        })
    return pd.DataFrame(rows)


def find_discharge_file():
    candidates = []
    for pattern in ["*.csv", "*.txt"]:
        candidates.extend(DISCHARGE_DIR.glob(pattern))
    candidates = sorted(
        candidates,
        key=lambda path: (
            "dmr" not in path.name.lower(),
            "summary" not in path.name.lower(),
            path.name.lower(),
        ),
    )
    for path in candidates:
        if path.name.lower().startswith("readme"):
            continue
        if path.stat().st_size == 0:
            continue
        return path
    return None


def parse_discharge_volume(wastewater_nj, watersheds_nj):
    discharge_file = find_discharge_file()
    if discharge_file is None:
        return pd.DataFrame(), pd.DataFrame([{
            "status": "missing_discharge_file",
            "required_folder": str(DISCHARGE_DIR),
            "accepted_note": "Place a DMR/discharge CSV with permit id and flow/load fields here, then rerun Step 20.",
        }]), pd.DataFrame()

    log(f"[DISCHARGE] Reading {discharge_file}")
    df = pd.read_csv(discharge_file, low_memory=False)
    columns_lower = {c.lower(): c for c in df.columns}

    permit_col = None
    for key in ["njpdes", "npdes", "permit", "permit_number", "npdes permit number"]:
        for lower, original in columns_lower.items():
            if key in lower:
                permit_col = original
                break
        if permit_col:
            break

    value_col = None
    for key in [
        "mean_dmr_flow_mgd",
        "total_dmr_flow_mgd",
        "mean_facility_discharge_value",
        "total_facility_discharge_value",
        "design_flow_mgd",
        "flow",
        "discharge",
        "quantity",
        "load",
        "volume",
        "mgd",
    ]:
        for lower, original in columns_lower.items():
            if key in lower and pd.api.types.is_numeric_dtype(pd.to_numeric(df[original], errors="coerce")):
                value_col = original
                break
        if value_col:
            break

    if permit_col is None or value_col is None:
        return pd.DataFrame(), pd.DataFrame([{
            "status": "unrecognized_discharge_schema",
            "file": str(discharge_file),
            "columns": "; ".join(df.columns),
            "accepted_note": "Need a permit id column and a numeric flow/discharge/load/volume column.",
        }]), pd.DataFrame()

    df["permit_id_clean"] = df[permit_col].apply(normalize_permit_id)
    df["discharge_value"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df[df["permit_id_clean"] != ""].copy()

    metric_map = {
        "dmr_flow_record_count": "discharge_record_count",
        "mean_dmr_flow_mgd": "mean_discharge_value",
        "total_dmr_flow_mgd": "total_discharge_value",
        "dmr_nitrogen_load_record_count": "nitrogen_load_record_count",
        "mean_dmr_nitrogen_load": "mean_nitrogen_load",
        "total_dmr_nitrogen_load": "total_nitrogen_load",
        "dmr_nitrogen_concentration_record_count": "nitrogen_concentration_record_count",
        "mean_dmr_nitrogen_concentration": "mean_nitrogen_concentration",
    }
    agg_spec = {}

    for source_col, output_col in metric_map.items():
        if source_col in df.columns:
            df[source_col] = pd.to_numeric(df[source_col], errors="coerce")
            agg_spec[output_col] = (
                source_col,
                "sum" if source_col.startswith("total_") or source_col.endswith("_count") else "mean",
            )

    if "mean_discharge_value" not in agg_spec:
        agg_spec["mean_discharge_value"] = ("discharge_value", "mean")
    if "total_discharge_value" not in agg_spec:
        agg_spec["total_discharge_value"] = ("discharge_value", "sum")
    if "discharge_record_count" not in agg_spec:
        agg_spec["discharge_record_count"] = ("discharge_value", "count")

    permit_summary = (
        df.dropna(subset=["permit_id_clean"])
        .groupby("permit_id_clean", as_index=False)
        .agg(**agg_spec)
    )

    facilities = wastewater_nj.copy()
    facilities["permit_id_clean"] = facilities["NJPDES"].apply(normalize_permit_id)
    facilities["permit_prefix"] = facilities["permit_id_clean"].str[:3].replace("", "unknown")
    facilities["facility_type_group"] = facilities.apply(classify_facility_type, axis=1)
    facilities = facilities.merge(permit_summary, on="permit_id_clean", how="left")
    facilities["dmr_match_status"] = np.where(
        facilities["mean_discharge_value"].notna(),
        "matched",
        "no_matching_dmr_permit_summary",
    )

    watershed_lookup = watersheds_nj[["watershed_name", "geometry"]].copy()
    joined = gpd.sjoin(facilities, watershed_lookup, how="left", predicate="within")
    joined["is_dmr_matched"] = joined["mean_discharge_value"].notna()
    joined["is_individual_npdes_like"] = joined["permit_id_clean"].str.match(r"^NJ0", na=False)
    joined["is_general_permit_like"] = joined["permit_id_clean"].str.match(r"^NJG", na=False)

    matched_joined = joined[joined["watershed_name"].notna()].copy()
    watershed_discharge = (
        matched_joined.groupby("watershed_name", as_index=False)
        .agg(
            total_facilities_with_permit_id=("permit_id_clean", lambda s: int((s != "").sum())),
            discharge_matched_facilities=("mean_discharge_value", lambda s: int(s.notna().sum())),
            dmr_matched_individual_permits=("permit_id_clean", lambda s: int(s[joined.loc[s.index, "is_dmr_matched"]].nunique())),
            discharge_record_count=("discharge_record_count", "sum"),
            mean_facility_discharge_value=("mean_discharge_value", "mean"),
            total_facility_discharge_value=("total_discharge_value", "sum"),
            nitrogen_load_record_count=("nitrogen_load_record_count", "sum") if "nitrogen_load_record_count" in joined.columns else ("permit_id_clean", "size"),
            mean_facility_nitrogen_load=("mean_nitrogen_load", "mean") if "mean_nitrogen_load" in joined.columns else ("permit_id_clean", "size"),
            total_facility_nitrogen_load=("total_nitrogen_load", "sum") if "total_nitrogen_load" in joined.columns else ("permit_id_clean", "size"),
            mean_facility_nitrogen_concentration=("mean_nitrogen_concentration", "mean") if "mean_nitrogen_concentration" in joined.columns else ("permit_id_clean", "size"),
        )
    )
    watershed_discharge["dmr_facility_match_rate_percent"] = (
        watershed_discharge["discharge_matched_facilities"]
        / watershed_discharge["total_facilities_with_permit_id"].replace(0, np.nan)
        * 100
    ).round(4)

    type_summary = (
        matched_joined.groupby(["watershed_name", "facility_type_group"], as_index=False)
        .agg(
            type_facilities=("permit_id_clean", "count"),
            type_dmr_matched_facilities=("is_dmr_matched", "sum"),
            type_total_discharge_value=("total_discharge_value", "sum"),
        )
    )
    for metric in ["type_facilities", "type_dmr_matched_facilities", "type_total_discharge_value"]:
        pivot = type_summary.pivot_table(
            index="watershed_name",
            columns="facility_type_group",
            values=metric,
            aggfunc="sum",
            fill_value=0,
        )
        pivot.columns = [f"{col}_{metric}" for col in pivot.columns]
        watershed_discharge = watershed_discharge.merge(pivot.reset_index(), on="watershed_name", how="left")

    match_summary = (
        joined.groupby(["permit_prefix", "facility_type_group"], as_index=False)
        .agg(
            total_facilities=("permit_id_clean", "count"),
            matched_facilities=("is_dmr_matched", "sum"),
            unique_facility_permits=("permit_id_clean", pd.Series.nunique),
        )
    )
    match_summary["match_rate_percent"] = (
        match_summary["matched_facilities"] / match_summary["total_facilities"].replace(0, np.nan) * 100
    ).round(4)
    match_summary["unmatched_reason"] = np.where(
        match_summary["permit_prefix"].eq("NJG"),
        "General permit IDs usually do not appear as facility-specific DMR permit summaries.",
        "No exact normalized permit match in the local DMR summary.",
    )

    facility_permits = set(joined.loc[joined["permit_id_clean"] != "", "permit_id_clean"])
    dmr_permits = set(permit_summary["permit_id_clean"])
    matched_permits = facility_permits & dmr_permits
    matched_facility_count = int(joined["is_dmr_matched"].sum())
    total_facility_count = int(len(joined))
    status = pd.DataFrame([{
        "status": "loaded",
        "file": str(discharge_file),
        "permit_column": permit_col,
        "value_column": value_col,
        "dmr_permit_count": int(len(dmr_permits)),
        "facility_permit_count": int(len(facility_permits)),
        "matched_unique_permits": int(len(matched_permits)),
        "matched_facilities": matched_facility_count,
        "total_facilities": total_facility_count,
        "facility_match_rate_percent": round(matched_facility_count / total_facility_count * 100, 4) if total_facility_count else 0,
        "permit_match_rate_percent": round(len(matched_permits) / len(facility_permits) * 100, 4) if facility_permits else 0,
        "matched_watersheds": int(watershed_discharge["discharge_matched_facilities"].gt(0).sum()),
        "general_permit_facilities": int(joined["is_general_permit_like"].sum()),
        "individual_npdes_like_facilities": int(joined["is_individual_npdes_like"].sum()),
        "outfall_location_status": "not_available_in_local_inputs",
        "flowline_network_status": "not_available_in_local_inputs",
        "method_note": "DMR values are joined by normalized permit ID to NJPDES facility points, then summarized by watershed and facility type.",
    }])
    return watershed_discharge, status, match_summary


def make_correlations(df):
    factor_cols = [
        "mean_annual_precip_inches",
        "p90_annual_precip_inches",
        "precip_cv",
        "watershed_area_km2_recomputed",
        "perimeter_km",
        "shape_compactness",
        "upgradient_facility_count_proxy",
        "upgradient_facility_density_proxy_per_100_km2",
        "mean_facility_discharge_value",
        "total_facility_discharge_value",
        "dmr_facility_match_rate_percent",
        "mean_facility_nitrogen_load",
        "total_facility_nitrogen_load",
        "mean_facility_nitrogen_concentration",
    ]
    target_cols = ["hotspot_rate_percent", "mean_nitrate_mg_L", "mean_p90_nitrate_mg_L"]
    rows = []
    for factor in factor_cols:
        if factor not in df.columns:
            continue
        for target in target_cols:
            if target not in df.columns:
                continue
            r = pearson(df[factor], df[target])
            rho = spearman(df[factor], df[target])
            n = df[[factor, target]].dropna().shape[0]
            rows.append({
                "factor_metric": factor,
                "nitrate_metric": target,
                "pearson_r": round(float(r), 4) if r is not None else None,
                "spearman_r": round(float(rho), 4) if rho is not None else None,
                "n": int(n),
            })
    return pd.DataFrame(rows)


def make_models(df):
    for col in df.columns:
        if col != "watershed_name":
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().any():
                df[col] = converted

    model_sets = {
        "developed_agriculture": ["developed_percent", "agriculture_percent"],
        "developed_agriculture_rainfall": ["developed_percent", "agriculture_percent", "mean_annual_precip_inches"],
        "developed_agriculture_hydro": ["developed_percent", "agriculture_percent", "shape_compactness"],
        "developed_agriculture_upgradient_proxy": ["developed_percent", "agriculture_percent", "upgradient_facility_density_proxy_per_100_km2"],
        "developed_agriculture_discharge": ["developed_percent", "agriculture_percent", "total_facility_discharge_value"],
        "developed_agriculture_nitrogen_load": ["developed_percent", "agriculture_percent", "total_facility_nitrogen_load"],
        "developed_agriculture_dmr_coverage": ["developed_percent", "agriculture_percent", "dmr_facility_match_rate_percent"],
    }
    targets = ["hotspot_rate_percent", "mean_nitrate_mg_L"]
    rows = []
    for target in targets:
        for model_name, predictors in model_sets.items():
            predictors = [p for p in predictors if p in df.columns]
            temp = df[["watershed_name", target] + predictors].dropna().copy()
            if len(temp) < len(predictors) + 3:
                continue
            z = temp[predictors].copy()
            z = (z - z.mean()) / z.std(ddof=0).replace(0, np.nan)
            z = z.fillna(0)
            X = np.column_stack([np.ones(len(z)), z.values])
            fit = ols_fit(X, temp[target].values)
            max_vif = calculate_vif(temp, predictors)
            rows.append({
                "target_metric": target,
                "model_name": model_name,
                "predictors": ", ".join(predictors),
                "n": int(fit["n"]),
                "r2": round(float(fit["r2"]), 4),
                "adjusted_r2": round(float(fit["adjusted_r2"]), 4),
                "rmse": round(float(fit["rmse"]), 4),
                "max_vif": round(float(max_vif), 4) if max_vif is not None else None,
                "vif_status": "acceptable" if max_vif is not None and max_vif < 5 else "too_high_or_unavailable",
            })
    return pd.DataFrame(rows)


def make_plots(joined, corr):
    if "mean_annual_precip_inches" in joined.columns:
        plt.figure(figsize=(8, 6))
        plt.scatter(joined["mean_annual_precip_inches"], joined["mean_nitrate_mg_L"])
        for _, row in joined.iterrows():
            plt.annotate(str(row["watershed_name"])[:18], (row["mean_annual_precip_inches"], row["mean_nitrate_mg_L"]), fontsize=7)
        plt.xlabel("Mean annual precipitation at watershed centroid (inches)")
        plt.ylabel("Mean nitrate (mg/L)")
        plt.title("Watershed-Level Rainfall vs Mean Nitrate")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(FIG_RAIN, dpi=200)
        plt.close()

    if "upgradient_facility_density_proxy_per_100_km2" in joined.columns:
        plt.figure(figsize=(8, 6))
        plt.scatter(joined["upgradient_facility_density_proxy_per_100_km2"], joined["hotspot_rate_percent"])
        plt.xlabel("Upgradient facility density proxy per 100 km2")
        plt.ylabel("Hotspot rate (%)")
        plt.title("Hydrology/Upgradient Proxy vs Hotspot Rate")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(FIG_HYDRO, dpi=200)
        plt.close()

    plot_corr = corr[corr["nitrate_metric"].isin(["hotspot_rate_percent", "mean_nitrate_mg_L"])].copy()
    plot_corr = plot_corr.dropna(subset=["pearson_r"]).copy()
    plot_corr["label"] = plot_corr["factor_metric"].str.replace("_", " ")
    plot_corr = plot_corr.reindex(plot_corr["pearson_r"].abs().sort_values(ascending=False).index).head(12)
    plt.figure(figsize=(11, 6))
    colors = ["#1d4ed8" if v >= 0 else "#b91c1c" for v in plot_corr["pearson_r"]]
    plt.barh(plot_corr["label"], plot_corr["pearson_r"], color=colors)
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("Pearson r")
    plt.title("Additional Factor Correlations")
    plt.tight_layout()
    plt.savefig(FIG_CORR, dpi=200)
    plt.close()


def main():
    ensure_dirs()
    log("========== Step 20: Discharge Volume, Watershed Rainfall, Hydrology/Upstream Proxy ==========")
    watersheds_wgs, watersheds_nj, wastewater_nj, base_joined = read_base_data()
    rainfall = fetch_watershed_rainfall(watersheds_wgs)
    hydro = hydrology_and_upstream_proxy(watersheds_nj, wastewater_nj)
    discharge, discharge_status, discharge_match_summary = parse_discharge_volume(wastewater_nj, watersheds_nj)

    joined = base_joined.merge(rainfall, on="watershed_name", how="left")
    joined = joined.merge(hydro, on="watershed_name", how="left")
    if not discharge.empty:
        joined = joined.merge(discharge, on="watershed_name", how="left")
    else:
        joined["total_facilities_with_permit_id"] = 0
        joined["discharge_matched_facilities"] = 0
        joined["dmr_matched_individual_permits"] = 0
        joined["dmr_facility_match_rate_percent"] = 0
        joined["mean_facility_discharge_value"] = np.nan
        joined["total_facility_discharge_value"] = np.nan
        joined["mean_facility_nitrogen_load"] = np.nan
        joined["total_facility_nitrogen_load"] = np.nan
        joined["mean_facility_nitrogen_concentration"] = np.nan

    fill_zero_cols = [
        "total_facilities_with_permit_id",
        "discharge_matched_facilities",
        "dmr_matched_individual_permits",
        "discharge_record_count",
        "nitrogen_load_record_count",
        "dmr_facility_match_rate_percent",
    ]
    for col in fill_zero_cols:
        if col in joined.columns:
            joined[col] = pd.to_numeric(joined[col], errors="coerce").fillna(0)

    corr = make_correlations(joined)
    models = make_models(joined)

    joined.to_csv(OUT_FACTOR_CSV, index=False)
    corr.to_csv(OUT_CORR_CSV, index=False)
    models.to_csv(OUT_MODEL_CSV, index=False)
    discharge_status.to_csv(OUT_PROCESSED / "discharge_volume_status.csv", index=False)
    discharge_match_summary.to_csv(OUT_DISCHARGE_MATCH_CSV, index=False)

    export_json(joined, OUT_FACTOR_JSON)
    export_json(corr, OUT_CORR_JSON)
    export_json(models, OUT_MODEL_JSON)
    export_json(discharge_status, OUT_DASHBOARD / "discharge_volume_status.json")
    export_json(discharge_match_summary, OUT_DISCHARGE_MATCH_JSON)
    make_plots(joined, corr)

    log("")
    log("========== Discharge Status ==========")
    log(discharge_status.to_string(index=False))
    log("")
    log("========== Strongest Additional Factor Correlations ==========")
    if not corr.empty:
        top = corr.dropna(subset=["pearson_r"]).reindex(corr.dropna(subset=["pearson_r"])["pearson_r"].abs().sort_values(ascending=False).index).head(12)
        log(top.to_string(index=False))
    log("")
    log(f"[EXPORT] {OUT_FACTOR_CSV}")
    log(f"[EXPORT] {OUT_CORR_CSV}")
    log(f"[EXPORT] {OUT_MODEL_CSV}")
    log(f"[EXPORT] {OUT_DISCHARGE_MATCH_CSV}")
    log(f"[EXPORT] {FIG_RAIN}")
    log(f"[EXPORT] {FIG_CORR}")
    log(f"[EXPORT] {FIG_HYDRO}")
    log("========== Step 20 Complete ==========")


if __name__ == "__main__":
    main()

import json
import glob
import warnings
from pathlib import Path

import pandas as pd
import geopandas as gpd

warnings.filterwarnings("ignore")


# ============================================================
# Step 12: Wastewater / NJPDES Facility Watershed Join
# Purpose:
#   Join NJPDES regulated facility locations to NJ watershed polygons.
#   Then merge facility counts with nitrate + land use watershed data.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

WASTEWATER_DIR = BASE_DIR / "data" / "external" / "wastewater"

POSSIBLE_WATERSHED_PATHS = [
    BASE_DIR / "data" / "external" / "watershed" / "nj_watershed_management_areas.geojson",
    BASE_DIR / "data" / "external" / "watershed_boundaries" / "nj_watershed_management_areas.geojson",
]

LAND_USE_NITRATE_PATH = BASE_DIR / "data" / "processed" / "watershed_land_use_nitrate_joined.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_LOGS = BASE_DIR / "output" / "logs"

OUT_FACILITY_SUMMARY_CSV = OUT_PROCESSED / "watershed_wastewater_facility_summary.csv"
OUT_JOINED_CSV = OUT_PROCESSED / "watershed_land_use_wastewater_nitrate_joined.csv"

OUT_FACILITY_SUMMARY_JSON = OUT_DASHBOARD / "watershed_wastewater_facility_summary.json"
OUT_JOINED_JSON = OUT_DASHBOARD / "watershed_land_use_wastewater_nitrate_joined.json"

LOG_PATH = OUT_LOGS / "12_wastewater_watershed_join_log.txt"


def log(message):
    print(message)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def ensure_dirs():
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.mkdir(parents=True, exist_ok=True)
    OUT_LOGS.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        LOG_PATH.unlink()


def find_watershed_file():
    for path in POSSIBLE_WATERSHED_PATHS:
        if path.exists():
            return path

    geojson_files = list((BASE_DIR / "data" / "external").glob("**/*watershed*.geojson"))

    if geojson_files:
        return geojson_files[0]

    raise FileNotFoundError(
        "Could not find watershed GeoJSON file. Expected one of:\n"
        + "\n".join(str(p) for p in POSSIBLE_WATERSHED_PATHS)
    )


def find_wastewater_file():
    direct_files = list(WASTEWATER_DIR.glob("*.shp"))

    if direct_files:
        return direct_files[0]

    recursive_files = glob.glob(str(WASTEWATER_DIR / "**" / "*.shp"), recursive=True)

    if recursive_files:
        return Path(recursive_files[0])

    raise FileNotFoundError(
        f"No wastewater shapefile found in:\n{WASTEWATER_DIR}\n\n"
        "Please place the NJPDES shapefile set in data/external/wastewater/"
    )


def check_shapefile_sidecars(shp_path):
    required = [".shp", ".shx", ".dbf"]
    recommended = [".prj"]

    missing_required = []
    missing_recommended = []

    for ext in required:
        file_path = shp_path.with_suffix(ext)

        if not file_path.exists():
            missing_required.append(str(file_path))

    for ext in recommended:
        file_path = shp_path.with_suffix(ext)

        if not file_path.exists():
            missing_recommended.append(str(file_path))

    if missing_required:
        raise FileNotFoundError(
            "Missing required shapefile sidecar files:\n"
            + "\n".join(missing_required)
        )

    if missing_recommended:
        log("WARNING: Missing .prj file. CRS may not be detected correctly.")

        for file in missing_recommended:
            log(file)


def pick_watershed_name_column(gdf):
    candidates = [
        "WMA_NAME",
        "WMA",
        "WMANAME",
        "NAME",
        "Name",
        "name",
        "BASIN",
        "BASIN_NAME",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    raise ValueError(
        "Could not find watershed name column. Available columns:\n"
        + "\n".join(gdf.columns)
    )


def clean_geometries(gdf, label):
    before = len(gdf)

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        gdf["geometry"] = gdf.geometry.buffer(0)

    after = len(gdf)

    log(f"{label} geometry clean: {before:,} -> {after:,}")

    return gdf


def guess_text_columns(gdf):
    """
    Some shapefile columns may show dtype as 'str' instead of pandas object.
    This function treats any non-geometry column with readable values as usable text.
    """

    text_cols = []

    for col in gdf.columns:
        if col == "geometry":
            continue

        sample_values = gdf[col].dropna().astype(str).head(10).tolist()

        if sample_values:
            text_cols.append(col)

    return text_cols


def classify_facility(row, text_cols):
    """
    Classify NJPDES facilities using DISTYPE first, then facility name fallback.

    DISTYPE groups used here are simplified research categories.
    They are intended for exploratory watershed-level analysis, not regulatory classification.
    """

    distype = str(row.get("DISTYPE", "")).upper().strip()
    facility_name = str(row.get("FACILITY", "")).upper().strip()

    # Main NJPDES code-based categories
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

    # Facility-name fallback
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
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def safe_get(row, col):
    if col in row.index:
        return row.get(col)

    return None


def main():
    ensure_dirs()

    log("========== Step 12: Wastewater / NJPDES Watershed Join ==========")

    watershed_path = find_watershed_file()
    wastewater_path = find_wastewater_file()
    check_shapefile_sidecars(wastewater_path)

    log(f"[READ] Watershed file: {watershed_path}")
    log(f"[READ] Wastewater/NJPDES file: {wastewater_path}")

    if not LAND_USE_NITRATE_PATH.exists():
        raise FileNotFoundError(
            f"Missing Step 10 joined file:\n{LAND_USE_NITRATE_PATH}\n\n"
            "Please run Step 10 first."
        )

    log(f"[READ] Land use + nitrate joined file: {LAND_USE_NITRATE_PATH}")

    watersheds = gpd.read_file(watershed_path)
    facilities = gpd.read_file(wastewater_path)

    log("")
    log("========== Watershed Columns ==========")
    for col in watersheds.columns:
        log(col)

    log("")
    log("========== Wastewater / NJPDES Columns ==========")
    for col in facilities.columns:
        log(col)

    log("")
    log("========== Wastewater / NJPDES Dtypes ==========")
    for col, dtype in facilities.dtypes.items():
        log(f"{col}: {dtype}")

    watershed_name_col = pick_watershed_name_column(watersheds)
    text_cols = guess_text_columns(facilities)

    log("")
    log(f"Selected watershed name column: {watershed_name_col}")
    log(f"Text columns used for facility classification: {text_cols}")

    if "DISTYPE" in facilities.columns:
        log("")
        log("========== DISTYPE Counts ==========")
        distype_counts = facilities["DISTYPE"].value_counts(dropna=False)

        for distype, count in distype_counts.items():
            log(f"{distype}: {count:,}")

    watersheds = clean_geometries(watersheds, "Watershed")
    facilities = clean_geometries(facilities, "Facilities")

    if watersheds.crs is None:
        raise ValueError("Watershed file has no CRS.")

    if facilities.crs is None:
        raise ValueError(
            "Facility shapefile has no CRS. Make sure the .prj file is in the same folder."
        )

    log("")
    log(f"Watershed original CRS: {watersheds.crs}")
    log(f"Facilities original CRS: {facilities.crs}")

    target_crs = "EPSG:3424"

    watersheds = watersheds.to_crs(target_crs)
    facilities = facilities.to_crs(target_crs)

    watersheds = watersheds[[watershed_name_col, "geometry"]].copy()
    watersheds = watersheds.rename(columns={watershed_name_col: "watershed_name"})

    facilities["facility_type_group"] = facilities.apply(
        lambda row: classify_facility(row, text_cols),
        axis=1
    )

    log("")
    log("========== Facility Type Counts ==========")
    type_counts = facilities["facility_type_group"].value_counts(dropna=False)

    for group, count in type_counts.items():
        log(f"{group}: {count:,}")

    keep_facility_cols = ["facility_type_group", "geometry"]

    for optional_col in ["FACILITY", "PI", "NJPDES", "DISTYPE"]:
        if optional_col in facilities.columns:
            keep_facility_cols.insert(-1, optional_col)

    facilities_for_join = facilities[keep_facility_cols].copy()
    facilities_for_join["facility_id_temp"] = range(1, len(facilities_for_join) + 1)

    log("")
    log("========== Spatial Join ==========")
    log("Joining NJPDES facilities to watershed polygons...")

    joined_points = gpd.sjoin(
        facilities_for_join,
        watersheds,
        how="left",
        predicate="within"
    )

    matched = joined_points["watershed_name"].notna().sum()
    unmatched = joined_points["watershed_name"].isna().sum()

    log(f"Facilities total: {len(joined_points):,}")
    log(f"Facilities matched to watershed: {matched:,}")
    log(f"Facilities not matched: {unmatched:,}")

    matched_points = joined_points[joined_points["watershed_name"].notna()].copy()

    total_summary = (
        matched_points
        .groupby("watershed_name", as_index=False)
        .agg(facility_count=("facility_id_temp", "count"))
    )

    type_summary = (
        matched_points
        .groupby(["watershed_name", "facility_type_group"], as_index=False)
        .agg(count=("facility_id_temp", "count"))
    )

    pivot = type_summary.pivot_table(
        index="watershed_name",
        columns="facility_type_group",
        values="count",
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    expected_types = [
        "industrial_stormwater",
        "septic_groundwater",
        "groundwater_discharge",
        "stormwater_or_surface",
        "residuals_or_recycling",
        "construction_or_permit",
        "mining_quarrying",
        "wastewater_treatment",
        "industrial_other",
        "other",
    ]

    for facility_type in expected_types:
        if facility_type not in pivot.columns:
            pivot[facility_type] = 0

    pivot = pivot.rename(columns={
        "industrial_stormwater": "industrial_stormwater_facility_count",
        "septic_groundwater": "septic_groundwater_facility_count",
        "groundwater_discharge": "groundwater_discharge_facility_count",
        "stormwater_or_surface": "stormwater_or_surface_facility_count",
        "residuals_or_recycling": "residuals_or_recycling_facility_count",
        "construction_or_permit": "construction_or_permit_facility_count",
        "mining_quarrying": "mining_quarrying_facility_count",
        "wastewater_treatment": "wastewater_treatment_facility_count",
        "industrial_other": "industrial_other_facility_count",
        "other": "other_facility_count",
    })

    facility_summary = watersheds[["watershed_name", "geometry"]].copy()

    # EPSG:3424 area is in square feet.
    # Convert square feet to square kilometers.
    facility_summary["watershed_area_sqft"] = facility_summary.geometry.area
    facility_summary["watershed_area_km2"] = (
        facility_summary["watershed_area_sqft"] * 0.09290304 / 1_000_000
    )

    facility_summary = facility_summary.drop(columns=["geometry", "watershed_area_sqft"])

    facility_summary = facility_summary.merge(total_summary, on="watershed_name", how="left")
    facility_summary = facility_summary.merge(pivot, on="watershed_name", how="left")

    count_cols = [
        "facility_count",
        "industrial_stormwater_facility_count",
        "septic_groundwater_facility_count",
        "groundwater_discharge_facility_count",
        "stormwater_or_surface_facility_count",
        "residuals_or_recycling_facility_count",
        "construction_or_permit_facility_count",
        "mining_quarrying_facility_count",
        "wastewater_treatment_facility_count",
        "industrial_other_facility_count",
        "other_facility_count",
    ]

    for col in count_cols:
        if col not in facility_summary.columns:
            facility_summary[col] = 0

        facility_summary[col] = facility_summary[col].fillna(0).astype(int)

    facility_summary["facility_density_per_100_km2"] = (
        facility_summary["facility_count"] / facility_summary["watershed_area_km2"] * 100
    )

    facility_summary["industrial_stormwater_density_per_100_km2"] = (
        facility_summary["industrial_stormwater_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["septic_groundwater_density_per_100_km2"] = (
        facility_summary["septic_groundwater_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["groundwater_discharge_density_per_100_km2"] = (
        facility_summary["groundwater_discharge_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["stormwater_or_surface_density_per_100_km2"] = (
        facility_summary["stormwater_or_surface_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["residuals_or_recycling_density_per_100_km2"] = (
        facility_summary["residuals_or_recycling_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["construction_or_permit_density_per_100_km2"] = (
        facility_summary["construction_or_permit_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    facility_summary["mining_quarrying_density_per_100_km2"] = (
        facility_summary["mining_quarrying_facility_count"]
        / facility_summary["watershed_area_km2"]
        * 100
    )

    density_cols = [
        "watershed_area_km2",
        "facility_density_per_100_km2",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_density_per_100_km2",
        "residuals_or_recycling_density_per_100_km2",
        "construction_or_permit_density_per_100_km2",
        "mining_quarrying_density_per_100_km2",
    ]

    for col in density_cols:
        facility_summary[col] = facility_summary[col].fillna(0).round(4)

    land_use_nitrate = pd.read_csv(LAND_USE_NITRATE_PATH)

    if "watershed_name" not in land_use_nitrate.columns:
        raise ValueError("watershed_land_use_nitrate_joined.csv has no watershed_name column.")

    full_joined = land_use_nitrate.merge(
        facility_summary,
        on="watershed_name",
        how="left"
    )

    for col in count_cols:
        if col not in full_joined.columns:
            full_joined[col] = 0

        full_joined[col] = full_joined[col].fillna(0).astype(int)

    for col in density_cols:
        if col not in full_joined.columns:
            full_joined[col] = 0

        full_joined[col] = full_joined[col].fillna(0).round(4)

    facility_summary.to_csv(OUT_FACILITY_SUMMARY_CSV, index=False)
    full_joined.to_csv(OUT_JOINED_CSV, index=False)

    export_json(facility_summary, OUT_FACILITY_SUMMARY_JSON)
    export_json(full_joined, OUT_JOINED_JSON)

    log("")
    log("========== Join Check ==========")
    log(f"Watersheds in facility summary: {len(facility_summary):,}")
    log(f"Watersheds in full joined table: {len(full_joined):,}")
    log(f"Total facilities counted in watersheds: {facility_summary['facility_count'].sum():,}")

    log("")
    log("========== Top 10 Watersheds by Facility Count ==========")

    top_count = full_joined.sort_values("facility_count", ascending=False).head(10)

    for _, row in top_count.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"facility_count={safe_get(row, 'facility_count')} | "
            f"density_per_100_km2={safe_get(row, 'facility_density_per_100_km2')} | "
            f"industrial_stormwater={safe_get(row, 'industrial_stormwater_facility_count')} | "
            f"septic_groundwater={safe_get(row, 'septic_groundwater_facility_count')} | "
            f"groundwater_discharge={safe_get(row, 'groundwater_discharge_facility_count')} | "
            f"stormwater_or_surface={safe_get(row, 'stormwater_or_surface_facility_count')} | "
            f"mean_nitrate={safe_get(row, 'mean_nitrate_mg_L')} | "
            f"hotspot_rate={safe_get(row, 'hotspot_rate_percent')}"
        )

    log("")
    log("========== Top 10 Watersheds by Facility Density ==========")

    top_density = full_joined.sort_values(
        "facility_density_per_100_km2",
        ascending=False
    ).head(10)

    for _, row in top_density.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"density_per_100_km2={safe_get(row, 'facility_density_per_100_km2')} | "
            f"facility_count={safe_get(row, 'facility_count')} | "
            f"developed={safe_get(row, 'developed_percent')}% | "
            f"mean_nitrate={safe_get(row, 'mean_nitrate_mg_L')} | "
            f"hotspot_rate={safe_get(row, 'hotspot_rate_percent')}"
        )

    log("")
    log("========== Top 10 Watersheds by Industrial Stormwater Facility Count ==========")

    top_industrial_stormwater = full_joined.sort_values(
        "industrial_stormwater_facility_count",
        ascending=False
    ).head(10)

    for _, row in top_industrial_stormwater.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"industrial_stormwater={safe_get(row, 'industrial_stormwater_facility_count')} | "
            f"density={safe_get(row, 'industrial_stormwater_density_per_100_km2')} | "
            f"facility_count={safe_get(row, 'facility_count')} | "
            f"mean_nitrate={safe_get(row, 'mean_nitrate_mg_L')} | "
            f"hotspot_rate={safe_get(row, 'hotspot_rate_percent')}"
        )

    log("")
    log("========== Top 10 Watersheds by Septic / Groundwater Facility Count ==========")

    top_septic = full_joined.sort_values(
        "septic_groundwater_facility_count",
        ascending=False
    ).head(10)

    for _, row in top_septic.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"septic_groundwater={safe_get(row, 'septic_groundwater_facility_count')} | "
            f"density={safe_get(row, 'septic_groundwater_density_per_100_km2')} | "
            f"facility_count={safe_get(row, 'facility_count')} | "
            f"mean_nitrate={safe_get(row, 'mean_nitrate_mg_L')} | "
            f"hotspot_rate={safe_get(row, 'hotspot_rate_percent')}"
        )

    log("")
    log("========== Export Complete ==========")
    log(f"[EXPORT] {OUT_FACILITY_SUMMARY_CSV}")
    log(f"[EXPORT] {OUT_JOINED_CSV}")
    log(f"[EXPORT] {OUT_FACILITY_SUMMARY_JSON}")
    log(f"[EXPORT] {OUT_JOINED_JSON}")

    log("")
    log("Step 12 finished successfully.")


if __name__ == "__main__":
    main()